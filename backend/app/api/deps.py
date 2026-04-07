from typing import Annotated, Any

from fastapi import Depends, Body
from sqlalchemy.ext.asyncio import AsyncSession


from app.db import get_db
from app.knowledge import VectorDatabase, vector_db_factory
from app.providers import Model, model_factory
from app.services import ThreadService, RAGService, ProjectService, ChatService


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


def get_chat_thread_service(session: "SessionDeps") -> ThreadService:
    """依赖注入接口：提供 ThreadService 实例"""
    return ThreadService(session=session)


def get_rag_service(session: "SessionDeps", vector_db: "VectorDBDeps") -> RAGService:
    """依赖注入接口：提供 RAGService 实例"""
    return RAGService(session=session, vector_db=vector_db)


def get_project_service(session: "SessionDeps") -> ProjectService:
    """项目服务工厂函数，提供 ProjectService 实例"""
    return ProjectService(session=session)


def get_chat_service(
    llm_model: "ModelDeps",
    thread_service: "ThreadServiceDeps",
    rag_service: "RAGServiceDeps",
) -> ChatService:
    """聊天服务工厂函数，提供 ChatService 实例"""
    return ChatService(
        llm_model=llm_model,
        thread_service=thread_service,
        rag_service=rag_service,
    )


# 数据库会话依赖
SessionDeps = Annotated[AsyncSession, Depends(get_db)]
# LLM 模型依赖
ModelDeps = Annotated[Model[Any], Depends(get_model)]
# 向量库依赖
VectorDBDeps = Annotated[VectorDatabase, Depends(get_vector_db)]
# 对话服务依赖
ThreadServiceDeps = Annotated[ThreadService, Depends(get_chat_thread_service)]
# 项目服务依赖
ProjectServiceDeps = Annotated[ProjectService, Depends(get_project_service)]
# RAG 服务依赖
RAGServiceDeps = Annotated[RAGService, Depends(get_rag_service)]
# 聊天服务依赖
ChatServiceDeps = Annotated[ChatService, Depends(get_chat_service)]
