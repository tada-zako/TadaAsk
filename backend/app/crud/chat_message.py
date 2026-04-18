from typing import Sequence, Literal, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatMessages


async def get_messages_by_session_id(
    session: AsyncSession,
    *,
    chat_session_id: int,
    limit: int = 10,
    offset: int = 0,
) -> Sequence[ChatMessages]:
    """
    获取指定 chat_session_id 的历史消息列表，按照 created_at 和 id 降序排序（即最新的消息在前）
    """
    result = await session.execute(
        select(ChatMessages)
        .where(ChatMessages.chat_session_id == chat_session_id)
        .offset(offset)
        .limit(limit)
        .order_by(ChatMessages.created_at.desc(), ChatMessages.id.desc())
    )
    return result.scalars().all()


async def save_chat_to_db(
    session: AsyncSession,
    *,
    role: Literal["user", "assistant"],
    message: str,
    chat_session_id: int,
    citation: dict[str, Any] | None = None,
) -> None:
    """将聊天消息保存到数据库"""
    new_message = ChatMessages(
        role=role,
        message=message,
        chat_session_id=chat_session_id,
        citation=citation,
    )
    session.add(new_message)
