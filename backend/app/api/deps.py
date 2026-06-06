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
)
from app.storage import FileStorage
from app.parser import FileParserFactory
from app.rag import (
    VectorDatabase,
    TextSplitter,
    FTSProvider,
    EmbeddingProvider,
    RerankProvider,
)
from app.services.rag import DocumentIngestService


# =========== 全局服务依赖注入接口 ============
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


async def valid_project(
    project_crud: Annotated[ProjectCRUD, Depends(get_project_crud)],
    project_uid: Annotated[str, Path(..., description="Project UID")],
) -> Project:
    """验证项目 UID 是否有效，返回项目实例或抛出 HTTPException"""
    project = await project_crud.get_project_by_uid(project_uid=project_uid)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


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


# =========== 组合依赖 ===========
SessionDeps = Annotated[AsyncSession, Depends(get_db)]  # 数据库会话依赖
FileStorageDeps = Annotated[FileStorage, Depends(get_file_storage)]  # 文件存储依赖

VectorDBDeps = Annotated[VectorDatabase, Depends(get_vector_db)]  # 向量库依赖
TextSplitterDeps = Annotated[TextSplitter, Depends(get_text_splitter)]  # 文本分割器依赖
FTSProviderDeps = Annotated[FTSProvider, Depends(get_fts_provider)]  # 全文检索服务依赖
EmbeddingProviderDeps = Annotated[
    EmbeddingProvider, Depends(get_embedding_provider)
]  # 向量化服务依赖
RerankProviderDeps = Annotated[
    RerankProvider, Depends(get_rerank_provider)
]  # 重排序服务依赖
FileParserFactoryDeps = Annotated[
    FileParserFactory, Depends(get_file_parser_factory)
]  # 文件解析器工厂依赖

# CRUD 依赖
ProjectCRUDeps = Annotated[ProjectCRUD, Depends(get_project_crud)]
AdminCRUDeps = Annotated[AdminCRUD, Depends(get_admin_crud)]
ChatMessageCRUDeps = Annotated[ChatMessageCRUD, Depends(get_chat_message_crud)]
ChatSessionCRUDeps = Annotated[ChatSessionCRUD, Depends(get_chat_session_crud)]
SourceCRUDeps = Annotated[SourceCRUD, Depends(get_source_crud)]

# valid project 依赖
ValidProjectDeps = Annotated[Project, Depends(valid_project)]

# Service 依赖
DocumentIngestServiceDeps = Annotated[
    DocumentIngestService,
    Depends(get_document_ingest_service),
]
