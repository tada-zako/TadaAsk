from typing import Sequence, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatMessages, Threads


async def get_thread_history(
    session: AsyncSession,
    *,
    thread_uid: str,
    limit: int = 10,
    offset: int = 0,
) -> Sequence[ChatMessages]:
    """
    获取指定 thread_uid 的历史消息，并返回 ChatMessages 实例列表
    """
    result = await session.execute(
        select(ChatMessages)
        .join(Threads)
        .where(Threads.uid == thread_uid)
        .offset(offset)
        .limit(limit)
        .order_by(ChatMessages.created_at.desc(), ChatMessages.id.desc())
    )
    chats = result.scalars().all()

    # 反转序列，使最新消息在最后面
    return chats[::-1]


async def save_chat_to_db(
    session: AsyncSession,
    *,
    thread_id: int,
    role: Literal["user", "assistant"],
    message: str,
) -> None:
    """将聊天消息保存到数据库"""
    chat = ChatMessages(thread_id=thread_id, role=role, message=message)
    session.add(chat)
