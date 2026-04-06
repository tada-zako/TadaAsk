from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import (
    WorkspaceThreads,
    WorkspaceChats,
)
from app.core.schemas import (
    WorkspaceChatRead,
    WorkspaceChatInternal,
    WorkspaceThreadCreate,
    WorkspaceThreadRead,
)
from app.core.config import settings
from app.utils.context_window import build_history_context_window


class ChatThreadService:
    async def create_thread(
        self, session: AsyncSession, thread_data: WorkspaceThreadCreate
    ) -> WorkspaceThreadRead:
        """创建新的聊天线程，并返回 thread_uid"""
        new_thread = WorkspaceThreads(**thread_data.model_dump())
        session.add(new_thread)
        await session.flush()  # 获取新线程的 UID
        return WorkspaceThreadRead.model_validate(new_thread)

    async def get_threads(
        self, session: AsyncSession, *, limit: int = 5, offset: int = 0
    ) -> list[WorkspaceThreadRead]:
        """获取所有聊天线程列表"""
        result = await session.execute(
            select(WorkspaceThreads)
            .offset(offset)
            .limit(limit)
            .order_by(WorkspaceThreads.created_at.desc())
        )
        threads = result.scalars().all()
        return [WorkspaceThreadRead.model_validate(thread) for thread in threads]

    async def get_thread_history(
        self,
        session: AsyncSession,
        *,
        thread_uid: str,
        limit: int = 10,
        offset: int = 0,
    ) -> list[WorkspaceChatRead]:
        """
        获取指定 thread_uid 的历史消息，并转换成 WorkspaceChatRead 模式返回
        """
        result = await session.execute(
            select(WorkspaceChats)
            .join(WorkspaceThreads)
            .where(WorkspaceThreads.uid == thread_uid)
            .offset(offset)
            .limit(limit)
            .order_by(WorkspaceChats.created_at.desc(), WorkspaceChats.id.desc())
        )
        chats = result.scalars().all()

        # 反转序列，使最新消息在最后面
        return [WorkspaceChatRead.model_validate(chat) for chat in reversed(chats)]

    async def resolve_thread_context_by_uid(
        self, session: AsyncSession, thread_uid: str
    ) -> tuple[int, list[WorkspaceChatInternal]]:
        """统一解析 thread_uid，并返回 thread_id 与处理后的历史消息。"""
        thread_id = await self.get_thread_id_by_uid(session, thread_uid)
        chat_history = await self.get_processed_history(session, thread_id)
        return thread_id, chat_history

    async def get_thread_id_by_uid(self, session: AsyncSession, thread_uid: str) -> int:
        """根据 thread_uid 获取对应的 thread_id，供内部业务调用"""
        result = await session.execute(
            select(WorkspaceThreads.id).where(WorkspaceThreads.uid == thread_uid)
        )
        thread_id = result.scalar_one_or_none()
        if thread_id is None:
            raise ValueError(f"Thread with uid {thread_uid} does not exist")
        return thread_id

    async def get_processed_history(
        self, session: AsyncSession, thread_id: int
    ) -> list[WorkspaceChatInternal]:
        """
        获取指定 thread_id 的历史消息：
        并进行必要的处理（如文本裁剪、敏感信息过滤等），返回处理后的消息列表
        用于内部 LLM 历史对话重建，省略了 workspace_id 等无关字段
        """
        result = await session.execute(
            select(WorkspaceChats)
            .where(WorkspaceChats.thread_id == thread_id)
            .order_by(WorkspaceChats.created_at.desc(), WorkspaceChats.id.desc())
            .limit(settings.sql_history_fetch_limit)
        )
        chats = result.scalars().all()

        # 返回处理后的历史消息列表
        return build_history_context_window(
            chats,
            max_context_tokens=settings.max_context_tokens,
            max_single_message_tokens=settings.max_single_message_tokens,
            model_name=settings.gemini_model_perf,
        )

    async def save_chat_to_db(
        self,
        session: AsyncSession,
        *,
        thread_id: int,
        role: Literal["user", "assistant"],
        message: str,
    ) -> None:
        """将聊天消息保存到数据库"""
        chat = WorkspaceChats(thread_id=thread_id, role=role, message=message)
        session.add(chat)


def get_chat_thread_service() -> ChatThreadService:
    """依赖注入接口：提供 ChatThreadService 实例"""
    return ChatThreadService()
