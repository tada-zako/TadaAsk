from typing import AsyncIterable

from fastapi import APIRouter
from loguru import logger

from ..schemas import ChatRequest
from ..deps import ChatServiceDeps


router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("/{thread_uid}/message")
async def stream_chat(
    thread_uid: str,
    chat_request: ChatRequest,
    chat_service: ChatServiceDeps,
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

    async with chat_service.stream_chat_reply(
        thread_uid=thread_uid,
        collection_uid=chat_request.collection_uid,
        user_message=chat_request.message,
        top_k=chat_request.doc_top_k,
    ) as chat_result:
        # 开启异步上下文，迭代异步生成器输出结果
        async for chunk in chat_result.stream_reply():
            yield chunk
