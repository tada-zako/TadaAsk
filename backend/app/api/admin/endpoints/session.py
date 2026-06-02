from typing import Annotated

from fastapi import APIRouter, Query, Path, Depends, HTTPException
from loguru import logger

from ...deps import (
    ValidProjectDeps,
    ChatSessionCRUDeps,
    ChatMessageCRUDeps,
)
from app.core.constants import ChatSessionType
from app.db.models import ChatSession
from app.db.schemas import ChatSessionRead, ChatMessageRead


router = APIRouter()


@router.get("/project/{project_uid}/sessions", response_model=list[ChatSessionRead])
async def list_chat_sessions(
    project: ValidProjectDeps,
    chat_session_crud: ChatSessionCRUDeps,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """
    获取项目下的聊天会话列表

    Args:
        project: 通过依赖注入获取的有效项目实例，这里只用于验证 project uid 的有效性
        chat_session_crud: 通过依赖注入获取的 ChatSessionCRUD 实例
        limit: 分页参数，限制返回的会话数量
        offset: 分页参数，指定返回会话的起始位置

    Returns:
        聊天会话列表
    """
    return await chat_session_crud.list_chat_sessions(
        session_type=ChatSessionType.ADMIN, limit=limit, offset=offset
    )


async def valid_admin_chat_session(
    chat_session_crud: ChatSessionCRUDeps,
    chat_session_uid: Annotated[
        str,
        Path(
            embed=True,
            alias="chatSessionUid",
            description="前端传递的 chat_session_uid",
        ),
    ],
) -> ChatSession:
    """
    Admin 端 ChatSession 依赖：
    验证 chat_session_uid 是否有效，返回对应的 ChatSession 实例。
    如果 chat_session_uid 为空或无效，报错
    """
    chat_session = await chat_session_crud.get_chat_session_by_uid(
        chat_session_uid=chat_session_uid
    )
    if chat_session:
        return chat_session
    else:
        logger.warning(
            f"Invalid chat_session_uid: {chat_session_uid}, creating new chat session"
        )
        raise ValueError("Invalid chat_session_uid, creating new chat session")


ChatSessionDeps = Annotated[ChatSession, Depends(valid_admin_chat_session)]


@router.get(
    "/session/{chat_session_uid}/messages", response_model=list[ChatMessageRead]
)
async def list_chat_messages(
    chat_session: ChatSessionDeps,
    chat_message_crud: ChatMessageCRUDeps,
    # 这里会话消息不允许外部分页，内部处理
    # limit: Annotated[int, Query(ge=1, le=100)] = 20,
    # offset: Annotated[int, Query(ge=0)] = 0,
):
    """
    获取聊天会话下的消息列表

    Args:
        chat_session: 通过依赖注入获取的有效聊天会话实例
        session: 数据库会话，通过依赖注入获取
        limit: 分页参数，限制返回的消息数量
        offset: 分页参数，指定返回消息的起始位置

    Returns:
        消息列表
    """
    # TODO: 这里的分页逻辑暂时固定为内部设置
    messages = await chat_message_crud.get_messages_by_session_id(
        chat_session_id=chat_session.id, limit=20, offset=0
    )
    return [ChatMessageRead.model_validate(message) for message in messages]


@router.delete("/session/{chat_session_uid}")
async def delete_chat_session(
    chat_session: ChatSessionDeps,
    chat_session_crud: ChatSessionCRUDeps,
):
    """
    删除聊天会话

    Args:
        chat_session: 通过依赖注入获取的有效聊天会话实例
        session: 数据库会话，通过依赖注入获取

    Returns:
        删除结果
    """
    success = await chat_session_crud.delete_chat_session_by_id(
        chat_session_id=chat_session.id
    )
    if success:
        return {"uid": chat_session.uid, "status": "deleted"}
    else:
        raise HTTPException(status_code=500, detail="Failed to delete chat session")
