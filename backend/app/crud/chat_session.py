from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatSessions
from app.db.schemas import ChatSessionCreate


async def create_chat_session(
    session: AsyncSession,
    chat_session_data: ChatSessionCreate,
) -> ChatSessions:
    """创建新的聊天会话，并返回创建的对话实例"""
    new_chat = ChatSessions(
        **chat_session_data.model_dump(),
    )
    session.add(new_chat)
    await session.flush()  # 获取新对话的 UID
    return new_chat


async def get_chat_sessions(
    session: AsyncSession, *, limit: int = 5, offset: int = 0
) -> Sequence[ChatSessions]:
    """获取所有聊天会话列表"""
    result = await session.execute(
        select(ChatSessions)
        .offset(offset)
        .limit(limit)
        .order_by(ChatSessions.created_at.desc())
    )
    return result.scalars().all()


async def get_chat_session_by_uid(
    session: AsyncSession, *, chat_session_uid: str
) -> ChatSessions | None:
    """根据 UID 获取指定的聊天会话"""
    result = await session.execute(
        select(ChatSessions).where(ChatSessions.uid == chat_session_uid)
    )
    return result.scalars().first()
