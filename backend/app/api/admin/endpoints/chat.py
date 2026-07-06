from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path

from ...deps import (
    ChatSessionOpsServiceDeps,
    ValidChatSessionDeps,
    ChatMessageCRUDeps,
)
from ...schemas import (
    AdminChatCancelResponse,
    AdminChatRevertResponse,
)
from app.db.models import ChatMessage
from app.core.exceptions import GenerationScopeError
from app.core.constants import (
    ChatMessageType,
    ChatMessageRole,
)


router = APIRouter()


async def valid_admin_chat_message(
    chat_session: ValidChatSessionDeps,
    chat_message_crud: ChatMessageCRUDeps,
    message_uid: Annotated[
        str,
        Path(description="目标 user message UID"),
    ],
) -> ChatMessage:
    """验证 Admin 端的 chat_message_uid 是否有效，返回对应的 ChatMessage 实例"""
    message = await chat_message_crud.get_message_by_uid_for_session(
        chat_session_id=chat_session.id, message_uid=message_uid
    )
    if not message:
        raise HTTPException(
            status_code=404,
            detail="Chat message not found",
        )

    if message.role != ChatMessageRole.USER:
        raise HTTPException(
            status_code=400,
            detail="Only user messages can be revert targets",
        )
    if message.type != ChatMessageType.MESSAGE:
        raise HTTPException(
            status_code=400,
            detail="Only normal messages can be revert targets",
        )

    return message


@router.post(
    "/session/{chat_session_uid}/messages/{message_uid}/revert",
    response_model=AdminChatRevertResponse,
)
async def revert_chat_session(
    chat_session: ValidChatSessionDeps,
    chat_session_ops: ChatSessionOpsServiceDeps,
    message: Annotated[ChatMessage, Depends(valid_admin_chat_message)],
):
    """回退聊天会话，删除目标 user message 及之后的消息"""
    deleted_count = await chat_session_ops.revert_session(
        chat_session=chat_session,
        message=message,
    )

    return AdminChatRevertResponse(
        session_uid=chat_session.uid,
        message_uid=message.uid,
        target_sequence=message.sequence,
        deleted_count=deleted_count,
    )


@router.get(
    "/session/{chat_session_uid}/messages/{message_uid}/citations",
    responses={
        501: {
            "description": "Reserved citation lazy-loading endpoint; implementation pending."
        }
    },
)
async def get_message_citations(
    _chat_session: ValidChatSessionDeps,
    message_uid: Annotated[
        str,
        Path(description="目标 assistant message UID"),
    ],
):
    """
    预留 citation 懒加载接口。

    后续实现应验证 message 属于当前 session，读取 ChatMessage.rag_snapshot，
    并在历史快照缺少展示字段时 join DocumentChunk / SourceItem / Source 补齐。
    """
    raise HTTPException(
        status_code=501,
        detail=(
            "Citation lazy-loading endpoint is reserved for future implementation."
        ),
    )


@router.post(
    "/session/{chat_session_uid}/generation/{generation_uid}/cancel",
    response_model=AdminChatCancelResponse,
)
async def cancel_admin_generation(
    chat_session: ValidChatSessionDeps,
    chat_session_ops: ChatSessionOpsServiceDeps,
    generation_uid: Annotated[
        str,
        Path(description="生成任务 UID"),
    ],
):
    """取消当前 admin session 下的活跃 LLM 生成；已结束时幂等 no-op"""
    try:
        cancelled = chat_session_ops.cancel_generation(
            chat_session=chat_session,
            generation_uid=generation_uid,
        )
    except GenerationScopeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return AdminChatCancelResponse(
        session_uid=chat_session.uid,
        generation_uid=generation_uid,
        cancelled=cancelled,
    )
