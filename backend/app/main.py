import uuid
from contextlib import asynccontextmanager
from functools import partial
from typing import Any, Mapping

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from loguru import logger

from app.core.config import Settings, settings
from app.core.logging import complete_logging, configure_logging
from app.core.request_logging import (
    RequestLoggingMiddleware,
    UnhandledExceptionMiddleware,
    internal_server_error_response,
)
from app.core.exceptions import RateLimitExceededError
from app.core.security import (
    get_password_hash,
    verify_password,
    ProviderAPIKeyCipher,
)
from app.core.rate_limit import VisitorRateLimiter
from app.crud import AdminCRUD, ModelProfileCRUD
from app.db import (
    async_session,
    get_db,
    get_session_factory,
    init_db,
    run_migrations,
)
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


tada_ask_logo = """
 ███████████               █████                █████████           █████
▒█▒▒▒███▒▒▒█              ▒▒███                ███▒▒▒▒▒███         ▒▒███
▒   ▒███  ▒   ██████    ███████   ██████      ▒███    ▒███   █████  ▒███ █████
    ▒███     ▒▒▒▒▒███  ███▒▒███  ▒▒▒▒▒███     ▒███████████  ███▒▒   ▒███▒▒███
    ▒███      ███████ ▒███ ▒███   ███████     ▒███▒▒▒▒▒███ ▒▒█████  ▒██████▒
    ▒███     ███▒▒███ ▒███ ▒███  ███▒▒███     ▒███    ▒███  ▒▒▒▒███ ▒███▒▒███
    █████   ▒▒████████▒▒████████▒▒████████    █████   █████ ██████  ████ █████
   ▒▒▒▒▒     ▒▒▒▒▒▒▒▒  ▒▒▒▒▒▒▒▒  ▒▒▒▒▒▒▒▒    ▒▒▒▒▒   ▒▒▒▒▒ ▒▒▒▒▒▒  ▒▒▒▒ ▒▒▒▒▒

"""


async def sync_admin_credentials(
    *,
    session_factory: async_sessionmaker[AsyncSession] = async_session,
    app_settings: Settings = settings,
) -> None:
    """启动时创建或同步由 Settings 管理的单一管理员凭据。"""
    async with session_factory() as session:
        async with session.begin():
            admin_crud = AdminCRUD(session)
            existing_admin = await admin_crud.get_admin_by_username(
                username=app_settings.admin_username
            )

            # 修改 ADMIN_USERNAME 后无法按新名称命中，此时复用最早创建的账号，
            # 避免每次改名都创建新的管理员记录。
            if existing_admin is None:
                existing_admin = await admin_crud.get_primary_admin()

            if existing_admin is None:
                # 不存在历史 admin 账号，创建新账号
                password_hash = get_password_hash(app_settings.admin_password)
                default_admin_data = AdminCreate(
                    username=app_settings.admin_username,
                    password_hash=password_hash,
                )
                new_admin = await admin_crud.create_admin(default_admin_data)
                logger.bind(
                    event="admin.credentials.created",
                    admin_uid=new_admin.uid,
                ).info("Admin credentials created from startup configuration")
                return

            username_changed = existing_admin.username != app_settings.admin_username
            password_changed = not verify_password(
                app_settings.admin_password,
                existing_admin.password_hash,
            )

            if not username_changed and not password_changed:
                # 用户名以及密码未更新
                logger.debug("Admin credentials already match startup configuration")
                return

            # 更新 username 或 password
            await admin_crud.update_credentials(
                existing_admin,
                username=app_settings.admin_username if username_changed else None,
                password_hash=(
                    get_password_hash(app_settings.admin_password)
                    if password_changed
                    else None
                ),
            )
            logger.bind(
                event="admin.credentials.updated",
                admin_uid=existing_admin.uid,
                username_changed=username_changed,
                password_changed=password_changed,
            ).info("Admin credentials updated from startup configuration")


async def sync_model_catalog(
    *,
    session_factory: async_sessionmaker[AsyncSession] = async_session,
    app_settings: Settings = settings,
) -> None:
    """在应用启动时同步 provider/model_profile 模型目录。"""
    async with session_factory() as session:
        async with session.begin():
            model_profile_service = ModelProfileService(
                model_profile_crud=ModelProfileCRUD(session=session)
            )
            await model_profile_service.sync_model_catalog(
                models_url=app_settings.models_url
            )


@asynccontextmanager
async def lifespan(
    app: FastAPI,
    *,
    session_factory: async_sessionmaker[AsyncSession] = async_session,
    app_settings: Settings = settings,
    initialize_runtime: bool = True,
    state_overrides: Mapping[str, Any] | None = None,
):
    """
    FastAPI 生命周期管理器，
    负责在应用启动时初始化数据库连接
    """

    logger.info("Application starting")

    if not initialize_runtime:
        # NOTE: 测试环境只挂载显式注入的组件，避免初始化模型、向量库和外部目录。
        # 该分支只服务于 tests 使用，避免全量初始化项目配置。
        for name, value in (state_overrides or {}).items():
            setattr(app.state, name, value)
        logger.info("Application started without runtime initialization")
        yield
        job_manager = getattr(app.state, "rag_job_manager", None)
        shutdown = getattr(job_manager, "shutdown", None)
        if shutdown:
            await shutdown()
        logger.info("Application stopping")
        await complete_logging()
        return

    # ======= 系统重要配置挂载 =======
    if app_settings.database_auto_migrate:
        logger.info("Database migration started")
        await run_migrations()
        logger.info("Database migration completed")

    await init_db()
    # MVP：管理员凭据以启动配置为准，暂不提供运行时修改 API。
    await sync_admin_credentials(
        session_factory=session_factory,
        app_settings=app_settings,
    )
    await sync_model_catalog(
        session_factory=session_factory,
        app_settings=app_settings,
    )

    # 挂载 visitor 限流器实例
    app.state.visitor_rate_limiter = VisitorRateLimiter(
        enabled=app_settings.visitor_rate_limit_enabled,
        ip_project_per_minute=app_settings.visitor_rate_limit_ip_project_per_minute,
        ip_project_per_hour=app_settings.visitor_rate_limit_ip_project_per_hour,
        ip_per_minute=app_settings.visitor_rate_limit_ip_per_minute,
        project_per_minute=app_settings.visitor_rate_limit_project_per_minute,
        stream_per_ip=app_settings.visitor_stream_concurrency_per_ip,
        stream_per_project=app_settings.visitor_stream_concurrency_per_project,
    )

    # 挂载文件存储实例
    file_storage: FileStorage = file_storage_factory(
        storage_backend=app_settings.file_storage_backend,
        base_path=app_settings.upload_folder_path,
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
        encryption_key=app_settings.provider_api_key_encryption_key,
        previous_keys=app_settings.provider_api_key_previous_encryption_keys,
    )
    app.state.api_key_cipher = api_key_cipher

    # ======= Chat Service 相关组件实例挂载 =======
    generation_registry = GenerationRegistry()
    app.state.generation_registry = generation_registry

    # ======= 初始化 RAG 组件实例 =======
    # 挂载向量库实例
    vector_db: VectorDatabase = vector_db_factory(
        vector_store=app_settings.vector_store_perf
    )
    app.state.vector_db = vector_db

    # 创建 embedding tokenizer 实例
    embedding_tokenizer: EmbeddingTokenizer = embedding_tokenizer_factory(
        embedding_mode=app_settings.embedding_backend,
        model_name=app_settings.embedding_model_name,
        cache_dir=app_settings.hf_hub_cache_dir,
    )

    # 挂载文本分割器实例
    text_splitter: TextSplitter = TokenAwareTextSplitter(
        tokenizer=embedding_tokenizer,
        chunk_tokens=app_settings.chunk_size_tokens,
        overlap_tokens=app_settings.chunk_overlap_tokens,
        window_tokens=app_settings.chunk_window_tokens,
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
        settings=app_settings
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
    rerank_provider: RerankProvider = rerank_provider_factory(settings=app_settings)
    app.state.rerank = rerank_provider

    # 挂载 TokenCounter 实例
    token_counter = TokenCounter(tokenizer=embedding_tokenizer)
    app.state.token_counter = token_counter

    # ======= Chat / RAG 在线对话服务挂载 =======
    context_builder = ContextBuilder(token_counter=token_counter)
    app.state.chat_context_builder = context_builder

    compaction_service = CompactionService(
        session_factory=session_factory,
        token_counter=token_counter,
    )
    app.state.compaction_service = compaction_service

    hybrid_search_service = HybridSearchService(
        session_factory=session_factory,
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
        session_factory=session_factory,
        context_builder=context_builder,
        generation_registry=generation_registry,
        compaction_service=compaction_service,
    )

    # ======= RAG 后台任务相关服务挂载 =======
    indexing_service = SourceItemIndexingService(
        session_factory=session_factory,
        file_storage=file_storage,
        file_parser_factory=file_parser_factory,
        vector_db=vector_db,
        text_splitter=text_splitter,
        embedding=embedding_provider,
        fts_provider=fts_search_provider,
    )
    app.state.source_item_indexing_service = indexing_service
    app.state.web_crawl_sync_service = WebCrawlSyncService(
        session_factory=session_factory,
        crawler=app.state.web_crawler,
        html_parser=app.state.html_page_parser,
        vector_db=vector_db,
    )
    app.state.rag_job_manager = RAGJobManager()

    for name, value in (state_overrides or {}).items():
        setattr(app.state, name, value)

    logger.info("Application started")
    logger.info(tada_ask_logo)
    yield  # 运行应用

    # await drop_db()  # 应用关闭时清理数据库连接
    # job manager 清理操作
    job_manager = getattr(app.state, "rag_job_manager", None)
    shutdown = getattr(job_manager, "shutdown", None)
    if shutdown:
        await shutdown()
    logger.info("Application stopping")
    await complete_logging()


def register_exception_handlers(app: FastAPI) -> None:
    """
    注册 FastAPI 自定义异常处理；
    使用装饰器语法糖进行自定义异常处理配置，集中注册应用异常处理器。
    """

    @app.exception_handler(ValueError)
    async def value_error_handler(_: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(RateLimitExceededError)
    async def rate_limit_exceeded_handler(
        _: Request, exc: RateLimitExceededError
    ) -> JSONResponse:
        """处理请求被限流的异常"""
        logger.bind(
            event="http.request.rate_limited",
            retry_after_seconds=exc.retry_after_seconds,
        ).warning("HTTP request rate limited")
        return JSONResponse(
            status_code=429,
            content={"detail": exc.message},
            headers={"Retry-After": str(exc.retry_after_seconds)},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler_override(
        request: Request, exc: StarletteHTTPException
    ):
        if exc.status_code >= 500:
            return _internal_server_error_response(request=request, exc=exc)
        return await http_exception_handler(request, exc)  # 调用默认的 HTTP 异常处理

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
        return _internal_server_error_response(request=request, exc=exc)


async def root():
    return {"message": "Hello World"}


def _internal_server_error_response(
    *,
    request: Request,
    exc: Exception,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", uuid.uuid4().hex)
    return internal_server_error_response(
        request_id=request_id,
        exc=exc,
    )


def create_app(
    *,
    session_factory: async_sessionmaker[AsyncSession] = async_session,
    app_settings: Settings = settings,
    initialize_runtime: bool = True,
    state_overrides: Mapping[str, Any] | None = None,
) -> FastAPI:
    """
    创建 FastAPI 应用；
    测试可注入隔离 session 和轻量运行时组件。
    """
    configure_logging(app_settings)

    app = FastAPI(
        lifespan=partial(
            lifespan,
            session_factory=session_factory,
            app_settings=app_settings,
            initialize_runtime=initialize_runtime,
            state_overrides=state_overrides,
        ),
        title="Tada Ask API",
    )

    # 未处理异常边界位于 CORS 内侧，使跨域前端也能读取安全的 500 响应。
    app.add_middleware(UnhandledExceptionMiddleware)
    # Admin 与 Widget 使用互斥的路径范围，避免响应头和信任策略相互叠加。
    app.add_middleware(
        AdminScopedCORSMiddleware,
        allow_origins=app_settings.admin_cors_origins,
    )
    app.add_middleware(
        WidgetScopedCORSMiddleware,
        session_factory=session_factory,
    )
    # 最后添加以包裹其他用户中间件，确保 CORS 预检和流式响应也具备请求日志。
    app.add_middleware(RequestLoggingMiddleware)

    # 注册自定义异常处理函数
    register_exception_handlers(app)

    app.include_router(admin.router, prefix="/admin", tags=["Admin"])
    app.include_router(visitor.router, prefix="/visitor", tags=["Visitor"])
    app.add_api_route("/", root, methods=["GET"])

    if session_factory is not async_session:
        # 测试环境手动覆盖数据库会话连接注入。
        async def get_test_db():
            async with session_factory() as session:
                async with session.begin():
                    yield session

        # 路由已经绑定原依赖函数，因此通过 FastAPI override 切换测试数据库。
        app.dependency_overrides[get_db] = get_test_db
        app.dependency_overrides[get_session_factory] = lambda: session_factory

    return app


app = create_app()
