from typing import AsyncIterable

from fastapi import APIRouter
from loguru import logger

from ..schemas import ChatRequest
from ..deps import ChatServiceDeps, ValidProjectDeps, ValidChatSessionDeps


router = APIRouter(tags=["Chat"])


@router.post("/project/{project_uid}/chat_session/{chat_session_uid}/stream_reply")
async def stream_chat(
    chat_request: ChatRequest,
    project: ValidProjectDeps,
    chat_session: ValidChatSessionDeps,
    chat_service: ChatServiceDeps,
) -> AsyncIterable[str]:
    """
    流式调用 LLM 生成聊天回复（无 Agent）

    Args:


    Returns:
        异步生成的聊天回复字符串流
    """
    logger.info(
        f"Received chat request: {chat_request} for project {project.id} and chat session {chat_session.uid}"
    )

    async with chat_service.stream_chat_reply(
        project=project,
        chat_session=chat_session,
        user_message=chat_request.message,
        top_k=chat_request.doc_top_k,
    ) as chat_result:
        # 开启异步上下文，迭代异步生成器输出结果
        async for chunk in chat_result.stream_reply():
            yield chunk
