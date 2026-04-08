from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatMessages, ChatSessions
from app.db.schemas import ChatMessageCreate


async def get_chat_history(
    session: AsyncSession,
    *,
    chat_session_uid: str,
    limit: int = 10,
    offset: int = 0,
) -> Sequence[ChatMessages]:
    """
    获取指定 chat_session_uid 的历史消息，并返回 ChatMessages 实例列表
    """
    result = await session.execute(
        select(ChatMessages)
        .join(ChatSessions)
        .where(ChatSessions.uid == chat_session_uid)
        .offset(offset)
        .limit(limit)
        .order_by(ChatMessages.created_at.desc(), ChatMessages.id.desc())
    )
    return result.scalars().all()


async def save_chat_to_db(
    session: AsyncSession,
    chat_message: ChatMessageCreate,
) -> None:
    """将聊天消息保存到数据库"""
    new_message = ChatMessages(**chat_message.model_dump())
    session.add(new_message)
