from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import HTTPException as StarletteHTTPException
from loguru import logger

from app.core.config import settings
from app.core.exceptions import RateLimitExceededError
from app.core.security import (
    get_password_hash,
    verify_password,
    ProviderAPIKeyCipher,
)
from app.core.rate_limit import VisitorRateLimiter
from app.crud import AdminCRUD, ModelProfileCRUD
from app.db import init_db, run_migrations, async_session
from app.db.schemas import AdminCreate
from app.storage import FileStorage, file_storage_factory
from app.ingestion.parser import (
    FileParserFactory,
    create_default_file_parser_factory,
)
from app.ingestion.crawler import WebCrawler, HTMLPageParser
from app.rag import (
    vector_db_factory,
    VectorDatabase,
    TextSplitter,
    TokenAwareTextSplitter,
    embedding_provider_factory,
    EmbeddingProvider,
    QueryExpander,
    rerank_provider_factory,
    RerankProvider,
    FTSProvider,
    SQLiteFTSProvider,
)
from app.rag.utils import FTSTokenizer, JiebaFTSTokenizer
from app.utils import embedding_tokenizer_factory, EmbeddingTokenizer, TokenCounter
from app.services.chat import (
    ChatOrchestratorService,
    CompactionService,
    ContextBuilder,
    GenerationRegistry,
)
from app.services.search import HybridSearchService, RAGRetrievalService
from app.services.model_profiles import ModelProfileService
from app.services.indexing import SourceItemIndexingService
from app.services.jobs import RAGJobManager
from app.services.sources import WebCrawlSyncService
from app.api import admin, visitor
from app.api.admin.cors import AdminScopedCORSMiddleware
from app.api.visitor.widget_cors import WidgetScopedCORSMiddleware


async def sync_admin_credentials():
    """启动时创建或同步由 Settings 管理的单一管理员凭据。"""
    async with async_session() as session:
        async with session.begin():
            admin_crud = AdminCRUD(session)
            existing_admin = await admin_crud.get_admin_by_username(
                username=settings.admin_username
            )

            # 修改 ADMIN_USERNAME 后无法按新名称命中，此时复用最早创建的账号，
            # 避免每次改名都创建新的管理员记录。
            if existing_admin is None:
                existing_admin = await admin_crud.get_primary_admin()

            if existing_admin is None:
                # 不存在历史 admin 账号，创建新账号
                password_hash = get_password_hash(settings.admin_password)
                default_admin_data = AdminCreate(
                    username=settings.admin_username,
                    password_hash=password_hash,
                )
                new_admin = await admin_crud.create_admin(default_admin_data)
                logger.info(f"默认管理员账号已创建，用户名：{new_admin.username}")
                return

            username_changed = existing_admin.username != settings.admin_username
            password_changed = not verify_password(
                settings.admin_password,
                existing_admin.password_hash,
            )

            if not username_changed and not password_changed:
                # 用户名以及密码未更新
                logger.info(f"管理员账号配置已同步，用户名：{settings.admin_username}")
                return

            # 更新 username 或 password
            await admin_crud.update_credentials(
                existing_admin,
                username=settings.admin_username if username_changed else None,
                password_hash=(
                    get_password_hash(settings.admin_password)
                    if password_changed
                    else None
                ),
            )
            logger.info(
                "管理员账号已按启动配置更新，"
                f"用户名变更：{username_changed}，密码变更：{password_changed}"
            )


async def sync_model_catalog():
    """在应用启动时同步 provider/model_profile 模型目录。"""
    async with async_session() as session:
        async with session.begin():
            model_profile_service = ModelProfileService(
                model_profile_crud=ModelProfileCRUD(session=session)
            )
            await model_profile_service.sync_model_catalog(
                models_url=settings.models_url
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 生命周期管理器，
    负责在应用启动时初始化数据库连接
    """

    logger.info("Starting up the application...")
    # ======= 系统重要配置挂载 =======
    if settings.database_auto_migrate:
        logger.info("Running database migrations...")
        await run_migrations()

    await init_db()
    # MVP：管理员凭据以启动配置为准，暂不提供运行时修改 API。
    await sync_admin_credentials()
    await sync_model_catalog()

    # 挂载 visitor 限流器实例
    app.state.visitor_rate_limiter = VisitorRateLimiter(
        enabled=settings.visitor_rate_limit_enabled,
        ip_project_per_minute=settings.visitor_rate_limit_ip_project_per_minute,
        ip_project_per_hour=settings.visitor_rate_limit_ip_project_per_hour,
        ip_per_minute=settings.visitor_rate_limit_ip_per_minute,
        project_per_minute=settings.visitor_rate_limit_project_per_minute,
        stream_per_ip=settings.visitor_stream_concurrency_per_ip,
        stream_per_project=settings.visitor_stream_concurrency_per_project,
    )

    # 挂载文件存储实例
    file_storage: FileStorage = file_storage_factory(
        storage_backend=settings.file_storage_backend,
    )
    app.state.file_storage = file_storage

    # 挂载文件解析器注册工厂
    file_parser_factory: FileParserFactory = create_default_file_parser_factory()
    app.state.file_parser_factory = file_parser_factory

    # 挂载 WebCrawler 实例
    app.state.web_crawler = WebCrawler(
        timeout=20.0,
        user_agent="TadaAsk/0.1",
    )

    # 挂载 HTMLPageParser 实例
    app.state.html_page_parser = HTMLPageParser()

    # 挂载密钥加密器实例
    api_key_cipher = ProviderAPIKeyCipher(
        encryption_key=settings.provider_api_key_encryption_key,
        previous_keys=settings.provider_api_key_previous_encryption_keys,
    )
    app.state.api_key_cipher = api_key_cipher

    # ======= Chat Service 相关组件实例挂载 =======
    generation_registry = GenerationRegistry()
    app.state.generation_registry = generation_registry

    # ======= 初始化 RAG 组件实例 =======
    # 挂载向量库实例
    vector_db: VectorDatabase = vector_db_factory(
        vector_store=settings.vector_store_perf
    )
    app.state.vector_db = vector_db

    # 创建 embedding tokenizer 实例
    embedding_tokenizer: EmbeddingTokenizer = embedding_tokenizer_factory(
        embedding_mode=settings.embedding_backend,
        model_name=settings.embedding_model_name,
        cache_dir=settings.hf_hub_cache_dir,
    )

    # 挂载文本分割器实例
    text_splitter: TextSplitter = TokenAwareTextSplitter(
        tokenizer=embedding_tokenizer,
        chunk_tokens=settings.chunk_size_tokens,
        overlap_tokens=settings.chunk_overlap_tokens,
        window_tokens=settings.chunk_window_tokens,
        splitter_strategy="ast",
    )
    app.state.text_splitter = text_splitter

    # 创建 FTS 分词器实例
    fts_tokenizer: FTSTokenizer = JiebaFTSTokenizer(
        cut_all=False,
        use_hmm=True,
        stop_words_file=None,
        jieba_stop_words_path=None,
        jieba_idf_path=None,
    )

    # 挂载 FTS Search Provider 实例
    fts_search_provider: FTSProvider = SQLiteFTSProvider(tokenizer=fts_tokenizer)
    app.state.fts_search_provider = fts_search_provider

    # 挂载 EmbeddingProvider 实例
    embedding_provider: EmbeddingProvider = embedding_provider_factory(
        settings=settings
    )
    app.state.embedding = embedding_provider
    # 挂载 QueryExpander 实例
    query_expander: QueryExpander = QueryExpander(
        prompt_version="prompt_v1",
        cache_enabled=True,
        cache_size=512,
        ttl_seconds=3600,
    )
    app.state.query_expander = query_expander
    # 挂载 RerankProvider 实例
    rerank_provider: RerankProvider = rerank_provider_factory(settings=settings)
    app.state.rerank = rerank_provider

    # 挂载 TokenCounter 实例
    token_counter = TokenCounter(tokenizer=embedding_tokenizer)
    app.state.token_counter = token_counter

    # ======= Chat / RAG 在线对话服务挂载 =======
    context_builder = ContextBuilder(token_counter=token_counter)
    app.state.chat_context_builder = context_builder

    compaction_service = CompactionService(
        session_factory=async_session,
        token_counter=token_counter,
    )
    app.state.compaction_service = compaction_service

    hybrid_search_service = HybridSearchService(
        session_factory=async_session,
        vector_db=vector_db,
        query_expander=query_expander,
        embedding=embedding_provider,
        fts_provider=fts_search_provider,
        rerank_provider=rerank_provider,
    )
    app.state.hybrid_search_service = hybrid_search_service

    rag_retrieval_service = RAGRetrievalService(
        hybrid_search_service=hybrid_search_service,
        token_counter=token_counter,
    )
    app.state.rag_retrieval_service = rag_retrieval_service

    app.state.chat_orchestrator_service = ChatOrchestratorService(
        session_factory=async_session,
        context_builder=context_builder,
        generation_registry=generation_registry,
        compaction_service=compaction_service,
    )

    # ======= RAG 后台任务相关服务挂载 =======
    indexing_service = SourceItemIndexingService(
        session_factory=async_session,
        file_storage=file_storage,
        file_parser_factory=file_parser_factory,
        vector_db=vector_db,
        text_splitter=text_splitter,
        embedding=embedding_provider,
        fts_provider=fts_search_provider,
    )
    app.state.source_item_indexing_service = indexing_service
    app.state.web_crawl_sync_service = WebCrawlSyncService(
        session_factory=async_session,
        crawler=app.state.web_crawler,
        html_parser=app.state.html_page_parser,
        vector_db=vector_db,
    )
    app.state.rag_job_manager = RAGJobManager()

    yield  # 运行应用

    # await drop_db()  # 应用关闭时清理数据库连接
    # job manager 清理操作
    await app.state.rag_job_manager.shutdown()
    logger.info("Shutting down the application...")


app = FastAPI(lifespan=lifespan, title="Tada Ask API")

# Admin 与 Widget 使用互斥的路径范围，避免响应头和信任策略相互叠加。
app.add_middleware(
    AdminScopedCORSMiddleware,
    allow_origins=settings.admin_cors_origins,
)
app.add_middleware(WidgetScopedCORSMiddleware, session_factory=async_session)


@app.exception_handler(ValueError)
async def value_error_handler(_: Request, exc: ValueError) -> JSONResponse:
    logger.warning(f"业务异常：{exc}")
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(RateLimitExceededError)
async def rate_limit_exceeded_handler(
    _: Request, exc: RateLimitExceededError
) -> JSONResponse:
    """处理请求被限流的异常"""
    logger.warning(
        f"请求被限流：{exc.message}，请在 {exc.retry_after_seconds} 秒后重试"
    )
    return JSONResponse(
        status_code=429,
        content={"detail": exc.message},
        headers={"Retry-After": str(exc.retry_after_seconds)},
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler_override(
    request: Request, exc: StarletteHTTPException
):
    logger.warning(f"HTTP异常：{exc.detail}，请求路径：{request.url.path}")
    return await http_exception_handler(request, exc)  # 调用默认的 HTTP 异常处理


@app.exception_handler(Exception)
async def generic_error_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception(f"未处理异常：{exc}")
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


# 注册路由
app.include_router(admin.router, prefix="/admin", tags=["Admin"])
app.include_router(visitor.router, prefix="/visitor", tags=["Visitor"])


@app.get("/")
async def root():
    logger.info("访问根路径 /")
    return {"message": "Hello World"}
