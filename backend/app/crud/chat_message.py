from typing import Sequence, Literal, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatMessage


class ChatMessageCRUD:
    """聊天消息的 CRUD 操作"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_messages_by_session_id(
        self,
        *,
        chat_session_id: int,
        limit: int = 10,
        offset: int = 0,
    ) -> Sequence[ChatMessage]:
        """
        获取指定 chat_session_id 的历史消息列表，按照 created_at 和 id 降序排序（即最新的消息在前）
        """
        result = await self.session.execute(
            select(ChatMessage)
            .where(ChatMessage.chat_session_id == chat_session_id)
            .offset(offset)
            .limit(limit)
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
        )
        return result.scalars().all()

    async def save_chat_to_db(
        self,
        *,
        role: Literal["user", "assistant"],
        message: str,
        chat_session_id: int,
        citation: dict[str, Any] | None = None,
    ) -> None:
        """将聊天消息保存到数据库"""
        new_message = ChatMessage(
            role=role,
            message=message,
            chat_session_id=chat_session_id,
            citation=citation,
        )
        self.session.add(new_message)
