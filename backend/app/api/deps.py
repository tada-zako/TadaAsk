from typing import Annotated

from fastapi import Depends, Request, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import get_db, get_session_factory
from app.db.models import Project
from app.crud import (
    ProjectCRUD,
    AdminCRUD,
    ChatMessageCRUD,
    ChatSessionCRUD,
    SourceCRUD,
    RAGSearchCRUD,
    ModelProfileCRUD,
)
from app.storage import FileStorage
from app.ingestion.parser import FileParserFactory
from app.ingestion.crawler import WebCrawler, HTMLPageParser
from app.rag import (
    VectorDatabase,
    TextSplitter,
    FTSProvider,
    EmbeddingProvider,
    RerankProvider,
    QueryExpander,
)
from app.utils import TokenCounter
from app.services.sources import (
    SourceItemUploadService,
    WebCrawlSyncService,
    SourceCreationService,
)
from app.services.indexing import SourceItemIndexingService
from app.services.search import HybridSearchService, RAGRetrievalService
from app.services.model_profiles import ModelProfileService
from app.services.chat import (
    ChatOrchestratorService,
    CompactionService,
    ContextBuilder,
    GenerationRegistry,
)
from app.core.config import settings
from app.core.security import ProviderAPIKeyCipher
from app.core.rate_limit import VisitorRateLimiter


# =========== 全局服务依赖注入接口 ============
def get_visitor_rate_limiter(request: Request) -> VisitorRateLimiter:
    """返回全局挂载的 VisitorRateLimiter 实例"""
    return request.app.state.visitor_rate_limiter


def get_api_key_cipher(request: Request) -> ProviderAPIKeyCipher:
    """返回全局挂载的 ProviderAPIKeyCipher 实例"""
    return request.app.state.api_key_cipher


def get_vector_db(request: Request) -> VectorDatabase:
    """返回全局挂载的向量数据库实例"""
    return request.app.state.vector_db


def get_generation_registry(request: Request) -> GenerationRegistry:
    """返回全局挂载的 GenerationRegistry 实例"""
    return request.app.state.generation_registry


def get_text_splitter(request: Request) -> TextSplitter:
    """返回全局挂载的文本分割器实例"""
    return request.app.state.text_splitter


def get_fts_provider(request: Request) -> FTSProvider:
    """返回全局挂载的全文检索服务实例"""
    return request.app.state.fts_search_provider


def get_embedding_provider(request: Request) -> EmbeddingProvider:
    """返回全局挂载的向量化服务实例"""
    return request.app.state.embedding


def get_query_expander(request: Request) -> QueryExpander:
    """返回全局挂载的查询扩展服务实例"""
    return request.app.state.query_expander


def get_rerank_provider(request: Request) -> RerankProvider:
    """返回全局挂载的重排序服务实例"""
    return request.app.state.rerank


def get_file_storage(request: Request) -> FileStorage:
    """返回全局挂载的文件存储实例"""
    return request.app.state.file_storage


def get_file_parser_factory(request: Request) -> FileParserFactory:
    """返回全局挂载的文件解析器工厂实例"""
    return request.app.state.file_parser_factory


def get_web_crawler(request: Request) -> WebCrawler:
    """返回全局挂载的 WebCrawler 实例"""
    return request.app.state.web_crawler


def get_html_page_parser(request: Request) -> HTMLPageParser:
    """返回全局挂载的 HTMLPageParser 实例"""
    return request.app.state.html_page_parser


def get_token_counter(request: Request) -> TokenCounter:
    """返回全局挂载的 TokenCounter 实例"""
    return request.app.state.token_counter


# ============ CRUD 依赖注入接口 ============
async def get_project_crud(session: "SessionDeps") -> ProjectCRUD:
    """依赖注入接口：提供 ProjectCRUD 实例"""
    return ProjectCRUD(session=session)


async def get_admin_crud(session: "SessionDeps") -> AdminCRUD:
    """依赖注入接口：提供 AdminCRUD 实例"""
    return AdminCRUD(session=session)


async def get_chat_message_crud(session: "SessionDeps") -> ChatMessageCRUD:
    """依赖注入接口：提供 ChatMessageCRUD 实例"""
    return ChatMessageCRUD(session=session)


async def get_chat_session_crud(session: "SessionDeps") -> ChatSessionCRUD:
    """依赖注入接口：提供 ChatSessionCRUD 实例"""
    return ChatSessionCRUD(session=session)


async def get_source_crud(session: "SessionDeps") -> SourceCRUD:
    """依赖注入接口：提供 SourceCRUD 实例"""
    return SourceCRUD(session=session)


async def get_rag_search_crud(session: "SessionDeps") -> RAGSearchCRUD:
    """依赖注入接口：提供 RAGSearchCRUD 实例"""
    return RAGSearchCRUD(session=session)


async def get_model_profile_crud(session: "SessionDeps") -> ModelProfileCRUD:
    """依赖注入接口：提供 ModelProfileCRUD 实例"""
    return ModelProfileCRUD(session=session)


# =========== 工具函数封装依赖注入接口 ===========
def get_client_ip(request: Request) -> str:
    """获取客户端 IP 地址"""
    if settings.visitor_trust_proxy_headers:
        # 信任代理头部信息
        # 优先尝试信任 Cloudflare
        cf_ip = request.headers.get("CF-Connecting-IP")
        if cf_ip:
            return cf_ip.strip()

        x_forwarded_for = request.headers.get("X-Forwarded-For")
        if x_forwarded_for:
            # 取第一个 IP
            return x_forwarded_for.split(",", 1)[0].strip()

    # fallback 到 request.client.host
    if request.client:
        return request.client.host

    return "unknown"


async def valid_project(
    project_crud: Annotated[ProjectCRUD, Depends(get_project_crud)],
    project_uid: Annotated[str, Path(..., description="Project UID")],
) -> Project:
    """验证项目 UID 是否有效，返回项目实例或抛出 HTTPException"""
    project = await project_crud.get_project_by_uid(project_uid=project_uid)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def valid_project_with_settings(
    project_crud: Annotated[ProjectCRUD, Depends(get_project_crud)],
    project_uid: Annotated[str, Path(..., description="Project UID")],
) -> Project:
    """验证项目 UID 是否有效，返回包含设置的项目实例或抛出 HTTPException"""
    project = await project_crud.get_project_with_settings_by_uid(
        project_uid=project_uid
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    settings = project.project_settings
    provider = settings.visitor_default_provider
    model_profile = settings.visitor_default_model_profile

    # 0. 校验项目默认提供商和模型配置是否存在
    if not provider or not model_profile:
        raise HTTPException(
            status_code=400,
            detail="Visitor default provider or model not configured for the project, please check if the project settings are properly initialized.",
        )

    # 1. 校验默认提供商是否启用
    if not provider.is_enabled:
        raise HTTPException(
            status_code=400,
            detail=f"The default model provider '{provider.name}' is currently disabled.",
        )

    # 2. 校验默认模型配置是否启用
    if not model_profile.is_enabled:
        raise HTTPException(
            status_code=400,
            detail=f"The default model '{model_profile.model}' is currently disabled.",
        )

    return project


# =========== Service 层依赖注入接口 ===========
def get_source_creation_service(
    source_crud: "SourceCRUDeps",
    vector_db: "VectorDBDeps",
) -> SourceCreationService:
    """SourceCreationService 依赖注入接口"""
    return SourceCreationService(
        source_crud=source_crud,
        vector_db=vector_db,
    )


def get_model_profile_service(
    model_profile_crud: "ModelProfileCRUDeps",
) -> ModelProfileService:
    """ModelProfileService 依赖注入接口"""
    return ModelProfileService(model_profile_crud=model_profile_crud)


def get_source_item_upload_service(
    source_crud: "SourceCRUDeps",
    file_storage: "FileStorageDeps",
) -> SourceItemUploadService:
    """SourceItemUploadService 依赖注入接口"""
    return SourceItemUploadService(
        source_crud=source_crud,
        file_storage=file_storage,
    )


def get_web_crawl_sync_service(
    source_crud: "SourceCRUDeps",
    crawler: "WebCrawlerDeps",
    html_parser: "HTMLPageParserDeps",
) -> WebCrawlSyncService:
    """WebCrawlSyncService 依赖注入接口"""
    return WebCrawlSyncService(
        source_crud=source_crud,
        crawler=crawler,
        html_parser=html_parser,
    )


def get_source_item_indexing_service(
    session_factory: "SessionFactoryDeps",
    file_storage: "FileStorageDeps",
    file_parser_factory: "FileParserFactoryDeps",
    vector_db: "VectorDBDeps",
    text_splitter: "TextSplitterDeps",
    embedding: "EmbeddingProviderDeps",
    fts_provider: "FTSProviderDeps",
) -> SourceItemIndexingService:
    """SourceItemIndexingService 依赖注入接口"""
    return SourceItemIndexingService(
        session_factory=session_factory,
        file_storage=file_storage,
        file_parser_factory=file_parser_factory,
        vector_db=vector_db,
        text_splitter=text_splitter,
        embedding=embedding,
        fts_provider=fts_provider,
    )


def get_hybrid_search_service(
    session: "SessionDeps",
    source_crud: "SourceCRUDeps",
    rag_search_crud: "RAGSearchCRUDeps",
    vector_db: "VectorDBDeps",
    query_expander: "QueryExpanderDeps",
    embedding: "EmbeddingProviderDeps",
    fts_provider: "FTSProviderDeps",
    rerank_provider: "RerankProviderDeps",
) -> HybridSearchService:
    """HybridSearchService 依赖注入接口"""
    return HybridSearchService(
        session=session,
        source_crud=source_crud,
        rag_search_crud=rag_search_crud,
        vector_db=vector_db,
        query_expander=query_expander,
        embedding=embedding,
        fts_provider=fts_provider,
        rerank_provider=rerank_provider,
    )


def get_rag_retrieval_service(
    rag_search_crud: "RAGSearchCRUDeps",
    hybrid_search_service: "HybridSearchServiceDeps",
    token_counter: "TokenCounterDeps",
) -> RAGRetrievalService:
    """RAGRetrievalService 依赖注入接口"""
    return RAGRetrievalService(
        rag_search_crud=rag_search_crud,
        hybrid_search_service=hybrid_search_service,
        token_counter=token_counter,
    )


def get_context_builder(
    token_counter: "TokenCounterDeps",
) -> ContextBuilder:
    """ContextBuilder 依赖注入接口"""
    return ContextBuilder(token_counter=token_counter)


def get_compaction_service(
    chat_message_crud: "ChatMessageCRUDeps",
    chat_session_crud: "ChatSessionCRUDeps",
    token_counter: "TokenCounterDeps",
) -> CompactionService:
    """CompactionService 依赖注入接口"""
    return CompactionService(
        chat_message_crud=chat_message_crud,
        chat_session_crud=chat_session_crud,
        token_counter=token_counter,
    )


def get_chat_orchestrator_service(
    session: "SessionDeps",
    chat_message_crud: "ChatMessageCRUDeps",
    chat_session_crud: "ChatSessionCRUDeps",
    context_builder: "ContextBuilderDeps",
    generation_registry: "GenerationRegistryDeps",
    compaction_service: "CompactionServiceDeps",
) -> ChatOrchestratorService:
    """ChatOrchestratorService 依赖注入接口"""
    return ChatOrchestratorService(
        session=session,
        chat_message_crud=chat_message_crud,
        chat_session_crud=chat_session_crud,
        context_builder=context_builder,
        generation_registry=generation_registry,
        compaction_service=compaction_service,
    )


# =========== 组合依赖 ===========
# 数据库会话依赖
SessionDeps = Annotated[AsyncSession, Depends(get_db)]
SessionFactoryDeps = Annotated[
    async_sessionmaker[AsyncSession], Depends(get_session_factory)
]

VisitorRateLimiterDeps = Annotated[
    VisitorRateLimiter, Depends(get_visitor_rate_limiter)
]
APIKeyCipherDeps = Annotated[ProviderAPIKeyCipher, Depends(get_api_key_cipher)]
FileStorageDeps = Annotated[FileStorage, Depends(get_file_storage)]

VectorDBDeps = Annotated[VectorDatabase, Depends(get_vector_db)]
GenerationRegistryDeps = Annotated[GenerationRegistry, Depends(get_generation_registry)]
TextSplitterDeps = Annotated[TextSplitter, Depends(get_text_splitter)]
FTSProviderDeps = Annotated[FTSProvider, Depends(get_fts_provider)]
EmbeddingProviderDeps = Annotated[EmbeddingProvider, Depends(get_embedding_provider)]
QueryExpanderDeps = Annotated[QueryExpander, Depends(get_query_expander)]
RerankProviderDeps = Annotated[RerankProvider, Depends(get_rerank_provider)]
FileParserFactoryDeps = Annotated[FileParserFactory, Depends(get_file_parser_factory)]
WebCrawlerDeps = Annotated[WebCrawler, Depends(get_web_crawler)]
HTMLPageParserDeps = Annotated[HTMLPageParser, Depends(get_html_page_parser)]
TokenCounterDeps = Annotated[TokenCounter, Depends(get_token_counter)]

# CRUD 依赖
ProjectCRUDeps = Annotated[ProjectCRUD, Depends(get_project_crud)]
AdminCRUDeps = Annotated[AdminCRUD, Depends(get_admin_crud)]
ChatMessageCRUDeps = Annotated[ChatMessageCRUD, Depends(get_chat_message_crud)]
ChatSessionCRUDeps = Annotated[ChatSessionCRUD, Depends(get_chat_session_crud)]
SourceCRUDeps = Annotated[SourceCRUD, Depends(get_source_crud)]
RAGSearchCRUDeps = Annotated[RAGSearchCRUD, Depends(get_rag_search_crud)]
ModelProfileCRUDeps = Annotated[ModelProfileCRUD, Depends(get_model_profile_crud)]


ClientIPDeps = Annotated[str, Depends(get_client_ip)]
# valid project 依赖
ValidProjectDeps = Annotated[Project, Depends(valid_project)]
ValidVisitorChatProjectDeps = Annotated[Project, Depends(valid_project_with_settings)]

# Service 依赖
SourceCreationServiceDeps = Annotated[
    SourceCreationService,
    Depends(get_source_creation_service),
]
ModelProfileServiceDeps = Annotated[
    ModelProfileService,
    Depends(get_model_profile_service),
]
SourceItemUploadServiceDeps = Annotated[
    SourceItemUploadService,
    Depends(get_source_item_upload_service),
]
WebCrawlSyncServiceDeps = Annotated[
    WebCrawlSyncService,
    Depends(get_web_crawl_sync_service),
]
SourceItemIndexingServiceDeps = Annotated[
    SourceItemIndexingService,
    Depends(get_source_item_indexing_service),
]
HybridSearchServiceDeps = Annotated[
    HybridSearchService,
    Depends(get_hybrid_search_service),
]
RAGRetrievalServiceDeps = Annotated[
    RAGRetrievalService,
    Depends(get_rag_retrieval_service),
]
ContextBuilderDeps = Annotated[
    ContextBuilder,
    Depends(get_context_builder),
]
CompactionServiceDeps = Annotated[
    CompactionService,
    Depends(get_compaction_service),
]
ChatOrchestratorServiceDeps = Annotated[
    ChatOrchestratorService,
    Depends(get_chat_orchestrator_service),
]
