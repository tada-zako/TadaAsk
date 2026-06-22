from typing import Sequence
from dataclasses import dataclass

from sqlalchemy import select, func, delete, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatMessage
from app.db.schemas import ChatMessageInternal, RAGSnapshot
from app.core.constants import ChatMessageRole, ChatMessageType


@dataclass
class ChatMessagesPageData:
    messages: list[ChatMessage]
    has_more_before: bool
    has_more_after: bool


class ChatMessageCRUD:
    """聊天消息的 CRUD 操作"""

    def __init__(self, session: AsyncSession):
        self.session = session

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

    async def _has_display_message(
        self,
        *,
        chat_session_id: int,
        include_internal: bool,
        before_sequence: int | None = None,
        after_sequence: int | None = None,
    ) -> bool:
        """
        检查指定方向是否还有可展示消息；
        通过查找指定 sequence 之前或之后的
        ChatMessage 来判断指定方向是否还有可展示消息
        """
        stmt = select(ChatMessage.id).where(
            ChatMessage.chat_session_id == chat_session_id
        )

        if not include_internal:
            # 只检索 MESSAGE 类型消息
            stmt = stmt.where(ChatMessage.type == ChatMessageType.MESSAGE)

        if before_sequence is not None:
            # 向前查找
            stmt = stmt.where(ChatMessage.sequence < before_sequence)

        if after_sequence is not None:
            # 向后查找
            stmt = stmt.where(ChatMessage.sequence > after_sequence)

        result = await self.session.execute(stmt.limit(1))  # 只返回至多一条
        return result.scalar_one_or_none() is not None

    async def list_messages_page(
        self,
        *,
        chat_session_id: int,
        limit: int,
        before_sequence: int | None = None,
        after_sequence: int | None = None,
        include_internal: bool = False,
    ) -> ChatMessagesPageData:
        """
        获取用于 UI timeline 展示的 cursor 分页消息；
        检索策略：
        - 如果提供了 before_sequence，则向前查找指定 sequence 之前的消息
        - 如果提供了 after_sequence，则向后查找指定 sequence 之后的消息
        - 如果 before_sequence 和 after_sequence 都不提供，则返回最新的 limit 条消息
        - 每次查询时多查询 limit + 1 条消息，用于判断是否还有更多消息可加载
        - 返回结果不包含 before_sequence 和 after_sequence 消息本身
        - 返回的消息列表按 sequence ASC 排序
        """
        if before_sequence is not None and after_sequence is not None:
            raise ValueError(
                "before_sequence and after_sequence cannot be used together"
            )

        # 1. 构建基础 Query
        stmt = select(ChatMessage).where(ChatMessage.chat_session_id == chat_session_id)
        if not include_internal:
            stmt = stmt.where(ChatMessage.type == ChatMessageType.MESSAGE)

        # 2. 判定分页查询方向 (True 代表向后，False 代表向前)
        is_asc = after_sequence is not None

        if is_asc:
            # 向后查询
            stmt = stmt.where(ChatMessage.sequence > after_sequence).order_by(
                ChatMessage.sequence.asc(), ChatMessage.id.asc()
            )
        else:
            # 向前查询或获取最新消息
            if before_sequence is not None:
                stmt = stmt.where(ChatMessage.sequence < before_sequence)
            stmt = stmt.order_by(ChatMessage.sequence.desc(), ChatMessage.id.desc())

        # 3. 执行查询 (统一 limit + 1)
        result = await self.session.execute(stmt.limit(limit + 1))
        rows = list(result.scalars().all())

        has_more_query_direction = (
            len(rows) > limit
        )  # 是否还有更多消息可加载（根据查询方向）
        sliced_rows = rows[:limit]

        # 4. 统一处理消息列表
        if is_asc:
            # 向后查询；查询结果已经是 ASC 排序
            messages = sliced_rows
            has_more_after = has_more_query_direction
            # 判断向前是否还有更多消息
            has_more_before = (
                await self._has_display_message(
                    chat_session_id=chat_session_id,
                    include_internal=include_internal,
                    before_sequence=messages[0].sequence,
                )
                if messages
                else False
            )
        else:
            # 向前查询或获取最新：查询结果是 DESC 排序，需要反转为 ASC
            messages = list(reversed(sliced_rows))
            has_more_before = has_more_query_direction

            if before_sequence is not None:
                # 判断向后是否还有更多消息
                has_more_after = (
                    await self._has_display_message(
                        chat_session_id=chat_session_id,
                        include_internal=include_internal,
                        after_sequence=messages[-1].sequence,
                    )
                    if messages
                    else False
                )
            else:
                # 获取最新消息；直接设为 False
                has_more_after = False

        return ChatMessagesPageData(
            messages=messages,
            has_more_before=has_more_before,
            has_more_after=has_more_after,
        )

    async def get_lastest_compaction_message(
        self,
        *,
        chat_session_id: int,
    ) -> ChatMessage | None:
        """获取最新的压缩消息；允许没有则返回 None"""
        stmt = (
            select(ChatMessage)
            .where(
                ChatMessage.chat_session_id == chat_session_id,
                ChatMessage.type == ChatMessageType.COMPACTION,
            )
            .order_by(ChatMessage.sequence.desc(), ChatMessage.id.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def load_recent_messages(
        self,
        *,
        chat_session_id: int,
        current_message: ChatMessage,
        compaction_message: ChatMessage | None = None,
    ) -> Sequence[ChatMessage]:
        """
        加载当前消息之前的最近消息；
        如果提供了 compaction_message
        则只加载 compaction_message.tail_start_sequence 之后的消息
        并且过滤掉 compaction_message 本身；
        """
        stmt = (
            select(ChatMessage)
            .where(
                ChatMessage.chat_session_id == chat_session_id,
                ChatMessage.sequence < current_message.sequence,
            )
            .order_by(ChatMessage.sequence.desc(), ChatMessage.id.desc())
        )

        if compaction_message is not None:
            stmt = stmt.where(
                ChatMessage.sequence >= compaction_message.tail_start_sequence,
                ChatMessage.id != compaction_message.id,
            )

        result = await self.session.execute(stmt)
        messages = result.scalars().all()
        return list(reversed(messages))  # 将消息列表反转为正序，便于构建对话上下文

    async def list_messages_until_sequence(
        self,
        *,
        chat_session_id: int,
        target_sequence: int,
    ) -> Sequence[ChatMessage]:
        """获取直到指定 sequence（包含）的历史消息列表"""
        stmt = (
            select(ChatMessage)
            .where(
                ChatMessage.chat_session_id == chat_session_id,
                ChatMessage.sequence <= target_sequence,
            )
            .order_by(ChatMessage.sequence.asc(), ChatMessage.id.asc())
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
        tail_start_sequence: int | None = None,
        rag_snapshot: RAGSnapshot | None = None,
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
                tail_start_sequence=tail_start_sequence,
                rag_snapshot=rag_snapshot,
            )
        )

    async def bulk_add_messages(
        self,
        *,
        messages_data: list[ChatMessageInternal],
    ):
        """批量添加消息"""
        if not messages_data:
            return
        messages_dicts = [msg_data.model_dump() for msg_data in messages_data]
        await self.session.execute(
            insert(ChatMessage),
            messages_dicts,
        )

    async def update_assistant_message(
        self,
        *,
        assistant_message: ChatMessage,
        new_message: str | None = None,
        new_rag_snapshot: RAGSnapshot | None = None,
    ) -> ChatMessage:
        """更新 assistant 消息内容"""
        if new_message is None and new_rag_snapshot is None:
            return assistant_message

        if new_message is not None:
            assistant_message.message = new_message

        if new_rag_snapshot is not None:
            assistant_message.rag_snapshot = new_rag_snapshot.model_dump()

        await self.session.flush()
        return assistant_message

    async def delete_messages_after_sequence(
        self,
        *,
        chat_session_id: int,
        target_sequence: int,
    ) -> int:
        """删除指定 sequence （包含）后的所有消息"""
        stmt = delete(ChatMessage).where(
            ChatMessage.chat_session_id == chat_session_id,
            ChatMessage.sequence >= target_sequence,
        )
        result = await self.session.execute(stmt)
        return result.rowcount or 0  # type: ignore
