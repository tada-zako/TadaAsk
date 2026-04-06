from typing import AsyncIterable

from fastapi import APIRouter
from loguru import logger

from ..schemas import ChatRequest
from ..deps import ModelDeps, ThreadServiceDeps, RAGServiceDeps
from app.services.chat import ChatService


router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("/{thread_uid}/message")
async def stream_chat(
    thread_uid: str,
    chat_request: ChatRequest,
    thread_service: ThreadServiceDeps,
    rag_service: RAGServiceDeps,
    llm_model: ModelDeps,
) -> AsyncIterable[str]:
    """
    流式调用 LLM 生成聊天回复（无 Agent）

    Args:
        thread_uid: 聊天线程 UID，从路径参数获取
        chat_request: 包含用户消息、RAG 检索使用的 collection_uid 和 doc_top_k 的请求体（NOTE: API 中使用驼峰命名）
        thread_service: 通过依赖注入获取 ThreadService 实例，用于获取历史消息和保存聊天记录
        rag_service: 通过依赖注入获取 RAGService 实例，用于向量库查询相关文档
        llm_model: 通过依赖注入获取 Model 实例，用于调用 LLM 接口生成回复

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
        thread_uid=thread_uid,
        collection_uid=chat_request.collection_uid,
        user_message=chat_request.message,
        top_k=chat_request.doc_top_k,
    ):
        yield chunk
