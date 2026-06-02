from typing import Annotated

from fastapi import Depends, Body, HTTPException, Path
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
from app.rag import VectorDatabase, vector_db_factory
from app.services import RAGService


def get_vector_db(
    vector_store_name: Annotated[
        str | None, Body(embed=True, alias="vectorStoreName")
    ] = None,
) -> VectorDatabase:
    """
    向量库工厂函数，根据配置返回对应的 VectorDatabase 实例。
    NOTE: 目前仅支持 ChromaDB。
    """

    return vector_db_factory(vector_store=vector_store_name)


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


def get_rag_service(session: "SessionDeps", vector_db: "VectorDBDeps") -> RAGService:
    """依赖注入接口：提供 RAGService 实例"""
    return RAGService(session=session, vector_db=vector_db)


# 数据库会话依赖
SessionDeps = Annotated[AsyncSession, Depends(get_db)]
# 向量库依赖
VectorDBDeps = Annotated[VectorDatabase, Depends(get_vector_db)]


# CRUD 依赖
ProjectCRUDeps = Annotated[ProjectCRUD, Depends(get_project_crud)]
AdminCRUDeps = Annotated[AdminCRUD, Depends(get_admin_crud)]
ChatMessageCRUDeps = Annotated[ChatMessageCRUD, Depends(get_chat_message_crud)]
ChatSessionCRUDeps = Annotated[ChatSessionCRUD, Depends(get_chat_session_crud)]
SourceCRUDeps = Annotated[SourceCRUD, Depends(get_source_crud)]


# valid project 依赖
ValidProjectDeps = Annotated[Project, Depends(valid_project)]
# RAG 服务依赖
RAGServiceDeps = Annotated[RAGService, Depends(get_rag_service)]
