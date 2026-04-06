from functools import lru_cache
from typing import Annotated, AsyncIterable, Any

from fastapi import APIRouter, Depends, Body
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from ..schemas import ChatRequest
from app.db.config import get_db
from app.core.config import settings
from app.providers import Model, GeminiModel
from app.services.thread import get_chat_thread_service, ChatThreadService
from app.services.rag import get_rag_service, RAGService
from app.services.chat import ChatService


router = APIRouter(prefix="/chat", tags=["Chat"])


@lru_cache(maxsize=8)
def _build_llm(provider: str, model: str | None) -> Model[Any]:
    if provider == "google":
        return GeminiModel(model_perf=model)
    raise ValueError(f"Unsupported LLM provider: {provider}")


def llm_factory(
    provider_name: Annotated[str | None, Body(embed=True, alias="providerName")] = None,
    model_name: Annotated[str | None, Body(embed=True, alias="modelName")] = None,
) -> Model[Any]:
    """
    LLM 工厂，根据 provider_name 返回对应的 LLM 实例。
    NOTE: 目前仅支持 GeminiModel。
    """
    p_name = (provider_name or settings.llm_provider_perf or "google").lower()
    return _build_llm(p_name, model_name)


@router.post("/{thread_uid}/message")
async def stream_chat(
    thread_uid: str,
    chat_request: ChatRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    thread_service: Annotated[ChatThreadService, Depends(get_chat_thread_service)],
    rag_service: Annotated[RAGService, Depends(get_rag_service)],
    llm_model: Annotated[Model[Any], Depends(llm_factory)],
) -> AsyncIterable[str]:
    """
    流式调用 LLM 生成聊天回复（无 Agent）

    Args:
        thread_uid: 聊天线程 UID，从路径参数获取
        chat_request: 包含用户消息、RAG 检索使用的 collection_uid 和 doc_top_k 的请求体（NOTE: API 中使用驼峰命名）
        session: 数据库会话，通过依赖注入获取
        thread_service: ChatThreadService 实例，通过依赖注入获取
        rag_service: RAGService 实例，通过依赖注入获取
        llm_model: Model 实例，通过工厂函数和依赖注入获取

    Returns:
        异步生成的聊天回复字符串流
    """
    logger.info(
        f"接收 chat 流式请求，thread_uid={thread_uid}, collection_uid={chat_request.collection_uid}, top_k={chat_request.doc_top_k}"
    )

    chat_service = ChatService(
        llm_model=llm_model,
        thread_service=thread_service,
        rag_service=rag_service,
    )

    async for chunk in chat_service.stream_chat_reply(
        session,
        thread_uid=thread_uid,
        collection_uid=chat_request.collection_uid,
        user_message=chat_request.message,
        top_k=chat_request.doc_top_k,
    ):
        yield chunk
