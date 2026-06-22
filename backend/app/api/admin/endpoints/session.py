from typing import Annotated

from fastapi import APIRouter, Query, Path, Depends, HTTPException

from ...deps import (
    ValidProjectDeps,
    ChatSessionCRUDeps,
    ChatMessageCRUDeps,
)
from app.db.models import ChatSession
from app.db.schemas import ChatSessionRead, ChatMessageRead, ChatMessagesPage


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
    sessions = await chat_session_crud.list_admin_project_sessions(
        project_id=project.id,
        limit=limit,
        offset=offset,
    )
    return [ChatSessionRead.model_validate(session) for session in sessions]


@router.get("/sessions", response_model=list[ChatSessionRead])
async def list_global_chat_sessions(
    chat_session_crud: ChatSessionCRUDeps,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """
    获取不带项目上下文的 Admin 聊天会话列表
    """
    sessions = await chat_session_crud.list_admin_global_sessions(
        limit=limit,
        offset=offset,
    )
    return [ChatSessionRead.model_validate(session) for session in sessions]


async def valid_admin_chat_session(
    chat_session_crud: ChatSessionCRUDeps,
    chat_session_uid: Annotated[
        str,
        Path(
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

    if not chat_session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    return chat_session


ValidChatSessionDeps = Annotated[ChatSession, Depends(valid_admin_chat_session)]


@router.get("/session/{chat_session_uid}/messages", response_model=ChatMessagesPage)
async def list_chat_messages(
    chat_session: ValidChatSessionDeps,
    chat_message_crud: ChatMessageCRUDeps,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    before_sequence: Annotated[
        int | None,
        Query(alias="beforeSequence", ge=1),
    ] = None,
    after_sequence: Annotated[
        int | None,
        Query(alias="afterSequence", ge=1),
    ] = None,
    include_internal: Annotated[
        bool,
        Query(alias="includeInternal", description="是否包含 compaction 等内部消息"),
    ] = False,
):
    """
    获取聊天会话下的消息 timeline 页面

    Args:
        chat_session: 通过依赖注入获取的有效聊天会话实例
        chat_message_crud: 通过依赖注入获取的 ChatMessageCRUD 实例
        limit: 单次返回的消息数量
        before_sequence: 向前加载指定 sequence 之前的消息
        after_sequence: 加载指定 sequence 之后的新消息
        include_internal: 是否包含 compaction 等内部消息

    NOTE:
        - before_sequence 和 after_sequence 都不传时，返回最新的 limit 条消息
        - before_sequence 和 after_sequence 不能同时使用，否则报错
        - 返回结果不包含 before_sequence 和 after_sequence 消息本身

    Returns:
        消息分页数据查找
    """
    if before_sequence is not None and after_sequence is not None:
        # 不能同时传输 before_sequence 和 after_sequence
        raise HTTPException(
            status_code=400,
            detail="beforeSequence and afterSequence cannot be used together",
        )

    # 分页方式查找消息记录
    page = await chat_message_crud.list_messages_page(
        chat_session_id=chat_session.id,
        limit=limit,
        before_sequence=before_sequence,
        after_sequence=after_sequence,
        include_internal=include_internal,
    )
    messages = [ChatMessageRead.model_validate(message) for message in page.messages]

    return ChatMessagesPage(
        messages=messages,
        has_more_before=page.has_more_before,
        has_more_after=page.has_more_after,
        oldest_sequence=messages[0].sequence if messages else None,
        newest_sequence=messages[-1].sequence if messages else None,
    )


@router.delete("/session/{chat_session_uid}")
async def delete_chat_session(
    chat_session: ValidChatSessionDeps,
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
