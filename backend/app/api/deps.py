from typing import Annotated, Any

from fastapi import Depends, Body
from sqlalchemy.ext.asyncio import AsyncSession


from app.core.config import settings
from app.db import get_db
from app.knowledge import VectorDatabase, ChromaDB
from app.providers import Model, GeminiModel
from app.services import ThreadService, RAGService, ProjectService


# 数据库会话依赖
SessionDeps = Annotated[AsyncSession, Depends(get_db)]


def model_factory(
    provider_name: Annotated[str | None, Body(embed=True, alias="providerName")] = None,
    model_name: Annotated[str | None, Body(embed=True, alias="modelName")] = None,
) -> Model[Any]:
    """
    model 工厂，根据 provider_name 返回对应的 Model 实例。
    NOTE: 目前仅支持 GeminiModel。
    """
    p_name = (provider_name or settings.llm_provider_perf or "google").lower()

    if p_name == "google":
        return GeminiModel(model_perf=model_name)
    raise ValueError(f"Unsupported LLM provider: {p_name}")


# LLM 模型依赖
ModelDeps = Annotated[Model[Any], Depends(model_factory)]


def vector_db_factory(
    vector_store_name: Annotated[
        str | None, Body(embed=True, alias="vectorStoreName")
    ] = None,
) -> VectorDatabase:
    """
    向量库工厂函数，根据配置返回对应的 VectorDatabase 实例。
    NOTE: 目前仅支持 ChromaDB。
    """
    v_name = (vector_store_name or settings.vector_store_perf or "chromadb").lower()

    if v_name == "chromadb":
        return ChromaDB()
    raise ValueError(f"Unsupported vector store provider: {v_name}")


# 向量库依赖
VectorDBDeps = Annotated[VectorDatabase, Depends(vector_db_factory)]


def get_chat_thread_service(session: SessionDeps) -> ThreadService:
    """依赖注入接口：提供 ThreadService 实例"""
    return ThreadService(session=session)


ThreadServiceDeps = Annotated[ThreadService, Depends(get_chat_thread_service)]


def get_rag_service(session: SessionDeps, vector_db: VectorDBDeps) -> RAGService:
    """依赖注入接口：提供 RAGService 实例"""
    return RAGService(session=session, vector_db=vector_db)


RAGServiceDeps = Annotated[RAGService, Depends(get_rag_service)]


def get_project_service(session: SessionDeps) -> ProjectService:
    """项目服务工厂函数，提供 ProjectService 实例"""
    return ProjectService(session=session)


ProjectServiceDeps = Annotated[ProjectService, Depends(get_project_service)]
