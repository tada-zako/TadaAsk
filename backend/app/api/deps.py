from typing import Annotated, Any

from fastapi import Depends, Body, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession


from app.db import get_db
from app.db.models import Projects
from app.crud import project_crud
from app.rag import VectorDatabase, vector_db_factory
from app.providers import Model, model_factory
from app.services import RAGService, ChatService


def get_model(
    provider_name: Annotated[str | None, Body(embed=True, alias="providerName")] = None,
    model_name: Annotated[str | None, Body(embed=True, alias="modelName")] = None,
) -> Model[Any]:
    """
    model 工厂，根据 provider_name 返回对应的 Model 实例。
    NOTE: 目前仅支持 GeminiModel。
    """
    return model_factory(provider=provider_name, model=model_name)


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


async def valid_project(
    project_uid: Annotated[str, Path(..., description="Project UID")],
    session: "SessionDeps",
) -> Projects:
    """验证项目 UID 是否有效，返回项目实例或抛出 HTTPException"""
    project = await project_crud.get_project_by_uid(
        session=session, project_uid=project_uid
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def get_rag_service(session: "SessionDeps", vector_db: "VectorDBDeps") -> RAGService:
    """依赖注入接口：提供 RAGService 实例"""
    return RAGService(session=session, vector_db=vector_db)


def get_chat_service(
    session: "SessionDeps",
    llm_model: "ModelDeps",
    rag_service: "RAGServiceDeps",
) -> ChatService:
    """聊天服务工厂函数，提供 ChatService 实例"""
    return ChatService(
        session,
        llm_model=llm_model,
        rag_service=rag_service,
    )


# 数据库会话依赖
SessionDeps = Annotated[AsyncSession, Depends(get_db)]
# LLM 模型依赖
ModelDeps = Annotated[Model[Any], Depends(get_model)]
# 向量库依赖
VectorDBDeps = Annotated[VectorDatabase, Depends(get_vector_db)]
# valid project 依赖
ValidProjectDeps = Annotated[Projects, Depends(valid_project)]
# RAG 服务依赖
RAGServiceDeps = Annotated[RAGService, Depends(get_rag_service)]
# 聊天服务依赖
ChatServiceDeps = Annotated[ChatService, Depends(get_chat_service)]
