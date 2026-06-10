from typing import Sequence, Any

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatMessage
from app.db.schemas import ChatMessageInternal
from app.core.constants import ChatMessageRole, ChatMessageType


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

    async def get_next_sequence(self, *, chat_session_id: int) -> int:
        """获取指定 chat_session_id 的下一条消息的 sequence"""
        stmt = select(func.max(ChatMessage.sequence)).where(
            ChatMessage.chat_session_id == chat_session_id
        )
        result = await self.session.execute(stmt)
        max_sequence = result.scalar_one_or_none()
        return 1 if max_sequence is None else max_sequence + 1

    async def list_messages_for_context(
        self,
        *,
        chat_session_id: int,
        limit: int | None = None,
    ) -> Sequence[ChatMessage]:
        """获取指定 chat_session_id 的历史消息列表用于构建对话上下文"""
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.chat_session_id == chat_session_id)
            .order_by(ChatMessage.sequence.desc(), ChatMessage.id.desc())
        )

        if limit is not None:
            stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)
        messages = result.scalars().all()
        return list(reversed(messages))  # 将消息列表反转为正序，便于构建对话上下文

    async def list_messages_for_display(
        self,
        *,
        chat_session_id: int,
        limit: int = 10,
        offset: int = 0,
    ) -> Sequence[ChatMessage]:
        """获取指定 chat_session_id 的历史消息列表用于 UI 展示"""
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.chat_session_id == chat_session_id)
            .order_by(ChatMessage.sequence.desc(), ChatMessage.id.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create_message(
        self,
        message_data: ChatMessageInternal,
    ) -> ChatMessage:
        """创建新的聊天消息，并返回创建的消息实例"""
        new_message = ChatMessage(
            **message_data.model_dump(),
        )
        self.session.add(new_message)
        await self.session.flush()  # 获取新消息的 UID
        return new_message

    async def append_message(
        self,
        *,
        chat_session_id: int,
        role: ChatMessageRole,
        message: str,
        provider: str,
        model: str,
        type: ChatMessageType = ChatMessageType.MESSAGE,
        citations: dict[str, Any] | None = None,
        rag_snapshot: dict[str, Any] | None = None,
    ) -> ChatMessage:
        """在指定 chat_session 追加新的 chat_message"""
        sequence = await self.get_next_sequence(chat_session_id=chat_session_id)

        return await self.create_message(
            ChatMessageInternal(
                chat_session_id=chat_session_id,
                sequence=sequence,
                role=role,
                message=message,
                type=type,
                provider=provider,
                model=model,
                citations=citations,
                rag_snapshot=rag_snapshot,
            )
        )

    async def delete_messages_after_sequence(
        self,
        *,
        chat_session_id: int,
        target_sequence: int,
    ) -> int:
        """删除指定 sequence 后的所有消息"""
        stmt = delete(ChatMessage).where(
            ChatMessage.chat_session_id == chat_session_id,
            ChatMessage.sequence > target_sequence,
        )
        result = await self.session.execute(stmt)
        return result.rowcount or 0  # type: ignore
