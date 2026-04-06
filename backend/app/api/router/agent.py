from functools import lru_cache
from typing import Annotated, AsyncIterable

from fastapi import APIRouter, Depends, Body
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic_ai.models import Model as AgentModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider
from loguru import logger

from ..schemas import AgentRequest
from app.db import get_db
from app.core.config import settings
from app.services.thread import get_chat_thread_service, ChatThreadService
from app.services.rag import get_rag_service, RAGService
from app.services.agent import AgentService


router = APIRouter(prefix="/agent", tags=["Agent"])


@lru_cache(maxsize=8)
def _build_agent_model(provider: str, model: str) -> AgentModel:
    logger.info(f"使用 {provider} 提供商的 {model} 模型实例化 AgentModel")
    if provider == "google":
        if not (key := settings.gemini_api_key):
            raise ValueError("Gemini API key is not set in the configuration.")
        return GoogleModel(model_name=model, provider=GoogleProvider(api_key=key))
    raise ValueError(f"Unsupported LLM provider for Agent: {provider}")


def agent_model_factory(
    provider_name: Annotated[str | None, Body(embed=True, alias="providerName")] = None,
    model_name: Annotated[str | None, Body(embed=True, alias="modelName")] = None,
) -> AgentModel:
    """
    Agent 模型工厂，用于外部注入模型实例
    NOTE: 目前仅支持 GoogleModel
    """
    p_name = (provider_name or settings.llm_provider_perf or "google").lower()
    m_name = (model_name or settings.gemini_model_perf or "gemini-2.5-flash").lower()
    return _build_agent_model(p_name, m_name)


@router.post("/{thread_uid}/agent")
async def stream_agent(
    thread_uid: str,
    chat_request: AgentRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    context_provider: Annotated[ChatThreadService, Depends(get_chat_thread_service)],
    rag_provider: Annotated[RAGService, Depends(get_rag_service)],
    llm_model: Annotated[AgentModel, Depends(agent_model_factory)],
) -> AsyncIterable[str]:
    """
    流式调用 Agent 进行对话

    Args:
        thread_uid: 聊天线程 UID，从路径参数获取
        chat_request: 包含用户消息、RAG 检索使用的 collection_uid 和 doc_top_k 的请求体（NOTE: API 中使用驼峰命名）
        session: 数据库会话，通过依赖注入获取
        context_provider: ChatThreadService 实例，作为 Agent 的上下文提供者，通过依赖注入获取
        rag_provider: RAGService 实例，作为 Agent 的检索工具，通过依赖注入获取
        llm_model: AgentModel 实例，作为 Agent 使用的语言模型，通过工厂函数和依赖注入获取

    Returns:
        异步生成的 Agent 回复字符串流
    """
    logger.info(
        f"接收 agent 流式请求，thread_uid={thread_uid}, collection_uid={chat_request.collection_uid}, "
        f"top_k={chat_request.doc_top_k}, mode={chat_request.mode}"
    )

    agent_service = AgentService(
        llm_model=llm_model,
        context_provider=context_provider,
        rag_provider=rag_provider,
    )

    async for chunk in agent_service.run_agent(
        session,
        thread_uid=thread_uid,
        collection_uid=chat_request.collection_uid,
        user_message=chat_request.message,
        mode=chat_request.mode,
    ):
        yield chunk
