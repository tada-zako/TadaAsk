from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Threads,
    ChatMessages,
)
from app.db.schemas import (
    ChatMessageRead,
    ChatMessageInternal,
    ThreadCreate,
    ThreadRead,
)
from app.core.config import settings
from app.tools.context_window import build_history_context_window


# TODO: 需要完整重构，新增的 Projects 模型尚未与 Service 集成


class ThreadService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # TODO: 对于这里的新对话创建逻辑，需要重新设计
    # 目前通过 API 直接通知后端创建，
    # 实际应该是由前端生成 thread_uid 后传给后端，后端根据 thread_uid 创建对应的线程记录
    # 也就是前端调用 chat/ API 时，业务层同时需要创建对应的 thread
    async def create_thread(self, thread_data: ThreadCreate) -> ThreadRead:
        """创建新的聊天线程，并返回 thread_uid"""
        new_thread = Threads(**thread_data.model_dump())
        self.session.add(new_thread)
        await self.session.flush()  # 获取新线程的 UID
        return ThreadRead.model_validate(new_thread)

    async def get_threads(self, *, limit: int = 5, offset: int = 0) -> list[ThreadRead]:
        """获取所有聊天线程列表"""
        result = await self.session.execute(
            select(Threads)
            .offset(offset)
            .limit(limit)
            .order_by(Threads.created_at.desc())
        )
        threads = result.scalars().all()
        return [ThreadRead.model_validate(thread) for thread in threads]

    async def get_thread_history(
        self,
        *,
        thread_uid: str,
        limit: int = 10,
        offset: int = 0,
    ) -> list[ChatMessageRead]:
        """
        获取指定 thread_uid 的历史消息，并转换成 ChatMessageRead 模式返回
        """
        result = await self.session.execute(
            select(ChatMessages)
            .join(Threads)
            .where(Threads.uid == thread_uid)
            .offset(offset)
            .limit(limit)
            .order_by(ChatMessages.created_at.desc(), ChatMessages.id.desc())
        )
        chats = result.scalars().all()

        # 反转序列，使最新消息在最后面
        return [ChatMessageRead.model_validate(chat) for chat in reversed(chats)]

    async def resolve_thread_context_by_uid(
        self, thread_uid: str
    ) -> tuple[int, list[ChatMessageInternal]]:
        """统一解析 thread_uid，并返回 thread_id 与处理后的历史消息。"""
        thread_id = await self.get_thread_id_by_uid(thread_uid)
        chat_history = await self.get_processed_history(thread_id)
        return thread_id, chat_history

    async def get_thread_id_by_uid(self, thread_uid: str) -> int:
        """根据 thread_uid 获取对应的 thread_id，供内部业务调用"""
        result = await self.session.execute(
            select(Threads.id).where(Threads.uid == thread_uid)
        )
        thread_id = result.scalar_one_or_none()
        if thread_id is None:
            raise ValueError(f"Thread with uid {thread_uid} does not exist")
        return thread_id

    async def get_processed_history(self, thread_id: int) -> list[ChatMessageInternal]:
        """
        获取指定 thread_id 的历史消息：
        并进行必要的处理（如文本裁剪、敏感信息过滤等），返回处理后的消息列表
        用于内部 LLM 历史对话重建，省略了 workspace_id 等无关字段
        """
        result = await self.session.execute(
            select(ChatMessages)
            .where(ChatMessages.thread_id == thread_id)
            .order_by(ChatMessages.created_at.desc(), ChatMessages.id.desc())
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
        *,
        thread_id: int,
        role: Literal["user", "assistant"],
        message: str,
    ) -> None:
        """将聊天消息保存到数据库"""
        chat = ChatMessages(thread_id=thread_id, role=role, message=message)
        self.session.add(chat)
