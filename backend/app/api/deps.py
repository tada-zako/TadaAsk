from typing import Annotated

from fastapi import Depends, Request, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
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
from app.providers import completer_factory, StructuredCompleter
from app.storage import FileStorage
from app.parser import FileParserFactory
from app.rag import (
    VectorDatabase,
    TextSplitter,
    FTSProvider,
    EmbeddingProvider,
    RerankProvider,
    QueryExpander,
    StandaloneQueryRewriter,
)
from app.utils import TokenCounter
from app.services.rag import (
    DocumentIngestService,
    HybridSearchService,
    RAGRetrievalService,
)
from app.services.chat import (
    ChatOrchestratorService,
    CompactionService,
    ContextBuilder,
    GenerationRegistry,
)
from app.core.security import ProviderAPIKeyCipher
from app.core.config import settings


# =========== 全局服务依赖注入接口 ============
def get_api_key_cipher(request: Request) -> ProviderAPIKeyCipher:
    """返回全局挂载的 ProviderAPIKeyCipher 实例"""
    return request.app.state.api_key_cipher


def get_vector_db(request: Request) -> VectorDatabase:
    """返回全局挂载的向量数据库实例"""
    return request.app.state.vector_db


def get_text_splitter(request: Request) -> TextSplitter:
    """返回全局挂载的文本分割器实例"""
    return request.app.state.text_splitter


def get_fts_provider(request: Request) -> FTSProvider:
    """返回全局挂载的全文检索服务实例"""
    return request.app.state.fts_search_provider


def get_embedding_provider(request: Request) -> EmbeddingProvider:
    """返回全局挂载的向量化服务实例"""
    return request.app.state.embedding


def get_rerank_provider(request: Request) -> RerankProvider:
    """返回全局挂载的重排序服务实例"""
    return request.app.state.rerank


def get_file_storage(request: Request) -> FileStorage:
    """返回全局挂载的文件存储实例"""
    return request.app.state.file_storage


def get_file_parser_factory(request: Request) -> FileParserFactory:
    """返回全局挂载的文件解析器工厂实例"""
    # TODO: 后续将 FileParserFactory 实例化逻辑放到 main.py; 使用注册器模式
    return request.app.state.file_parser_factory


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


async def valid_project(
    project_crud: Annotated[ProjectCRUD, Depends(get_project_crud)],
    project_uid: Annotated[str, Path(..., description="Project UID")],
) -> Project:
    """验证项目 UID 是否有效，返回项目实例或抛出 HTTPException"""
    project = await project_crud.get_project_by_uid(project_uid=project_uid)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


# =========== Provider 依赖注入接口 ============
def get_completer(
    provider_name: Annotated[
        str,
        Path(
            ...,
            description="Provider name, e.g. 'openai', 'google', 'deepseek', 'ollama'",
        ),
    ],
    model_name: Annotated[
        str,
        Path(
            ...,
            description="Model name, e.g. 'gpt-3.5-turbo', 'gemini-1.5-pro', 'ollama-mistral-7b-v0.1.Q4_0.gguf'",
        ),
    ],
) -> StructuredCompleter:
    """依赖注入接口：根据 provider_name 和 model_name 返回对应的 FullCompleter 实例"""
    p_name = provider_name or settings.llm_provider_admin or "google"

    if p_name == "google":
        m_name = model_name or settings.gemini_model_perf or "gemini-2.5-flash"
    elif p_name == "deepseek":
        m_name = model_name or settings.deepseek_model_perf or "DeepSeek-V4-Flash"
    else:
        m_name = model_name

    return completer_factory(provider=p_name, model=m_name)


def get_query_expander(
    completer: Annotated[StructuredCompleter, Depends(get_completer)],
) -> QueryExpander:
    """依赖注入接口：提供 QueryExpander 实例"""
    return QueryExpander(
        completer=completer,
        prompt_version="prompt_v1",
        cache_enabled=True,
        cache_size=512,
        ttl_seconds=3600,
    )


def get_standalone_rewriter(
    completer: Annotated[StructuredCompleter, Depends(get_completer)],
) -> StandaloneQueryRewriter:
    """依赖注入接口：提供 StandaloneQueryRewriter 实例"""
    return StandaloneQueryRewriter(completer=completer)


# =========== Service 层依赖注入接口 ===========
def get_document_ingest_service(
    source_crud: "SourceCRUDeps",
    file_storage: "FileStorageDeps",
    vector_db: "VectorDBDeps",
    text_splitter: "TextSplitterDeps",
    embedding: "EmbeddingProviderDeps",
    fts_provider: "FTSProviderDeps",
    file_parser_factory: "FileParserFactoryDeps",
) -> DocumentIngestService:
    """DocumentIngestService 依赖注入接口"""
    return DocumentIngestService(
        source_crud=source_crud,
        file_storage=file_storage,
        vector_db=vector_db,
        text_splitter=text_splitter,
        embedding=embedding,
        fts_provider=fts_provider,
        file_parser_factory=file_parser_factory,
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
    standalone_rewriter: "StandaloneQueryRewriterDeps",
    token_counter: "TokenCounterDeps",
) -> RAGRetrievalService:
    """RAGRetrievalService 依赖注入接口"""
    return RAGRetrievalService(
        rag_search_crud=rag_search_crud,
        hybrid_search_service=hybrid_search_service,
        standalone_rewriter=standalone_rewriter,
        token_counter=token_counter,
    )


# =========== 组合依赖 ===========
# 数据库会话依赖
SessionDeps = Annotated[AsyncSession, Depends(get_db)]

APIKeyCipherDeps = Annotated[ProviderAPIKeyCipher, Depends(get_api_key_cipher)]
FileStorageDeps = Annotated[FileStorage, Depends(get_file_storage)]

VectorDBDeps = Annotated[VectorDatabase, Depends(get_vector_db)]
TextSplitterDeps = Annotated[TextSplitter, Depends(get_text_splitter)]
FTSProviderDeps = Annotated[FTSProvider, Depends(get_fts_provider)]
EmbeddingProviderDeps = Annotated[EmbeddingProvider, Depends(get_embedding_provider)]
RerankProviderDeps = Annotated[RerankProvider, Depends(get_rerank_provider)]
FileParserFactoryDeps = Annotated[FileParserFactory, Depends(get_file_parser_factory)]
TokenCounterDeps = Annotated[TokenCounter, Depends(get_token_counter)]

# CRUD 依赖
ProjectCRUDeps = Annotated[ProjectCRUD, Depends(get_project_crud)]
AdminCRUDeps = Annotated[AdminCRUD, Depends(get_admin_crud)]
ChatMessageCRUDeps = Annotated[ChatMessageCRUD, Depends(get_chat_message_crud)]
ChatSessionCRUDeps = Annotated[ChatSessionCRUD, Depends(get_chat_session_crud)]
SourceCRUDeps = Annotated[SourceCRUD, Depends(get_source_crud)]
RAGSearchCRUDeps = Annotated[RAGSearchCRUD, Depends(get_rag_search_crud)]
ModelProfileCRUDeps = Annotated[ModelProfileCRUD, Depends(get_model_profile_crud)]

# valid project 依赖
ValidProjectDeps = Annotated[Project, Depends(valid_project)]

# Provider 依赖
QueryExpanderDeps = Annotated[QueryExpander, Depends(get_query_expander)]
StandaloneQueryRewriterDeps = Annotated[
    StandaloneQueryRewriter, Depends(get_standalone_rewriter)
]

# Service 依赖
DocumentIngestServiceDeps = Annotated[
    DocumentIngestService,
    Depends(get_document_ingest_service),
]
HybridSearchServiceDeps = Annotated[
    HybridSearchService,
    Depends(get_hybrid_search_service),
]
