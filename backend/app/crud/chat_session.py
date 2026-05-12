from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ChatSessionType
from app.db.models import ChatSession
from app.db.schemas import ChatSessionInternal


class ChatSessionCRUD:
    """聊天会话的 CRUD 操作"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_chat_session(
        self,
        chat_session_data: ChatSessionInternal,
    ) -> ChatSession:
        """创建新的聊天会话，并返回创建的对话实例"""
        new_chat = ChatSession(
            **chat_session_data.model_dump(),
        )
        self.session.add(new_chat)
        await self.session.flush()  # 获取新对话的 UID
        return new_chat

    async def get_chat_sessions(
        self,
        *,
        session_type: ChatSessionType,
        limit: int = 5,
        offset: int = 0,
    ) -> Sequence[ChatSession]:
        """获取指定类型聊天会话列表"""
        result = await self.session.execute(
            select(ChatSession)
            .where(ChatSession.session_type == session_type)
            .offset(offset)
            .limit(limit)
            .order_by(ChatSession.created_at.desc())
        )
        return result.scalars().all()

    async def get_chat_session_by_uid(
        self, chat_session_uid: str
    ) -> ChatSession | None:
        """根据 UID 获取指定的聊天会话"""
        result = await self.session.execute(
            select(ChatSession).where(ChatSession.uid == chat_session_uid)
        )
        return result.scalars().first()

    async def delete_chat_session_by_id(self, chat_session_id: int) -> bool:
        """根据聊天会话 ID 删除会话，返回是否删除成功"""
        result = await self.session.execute(
            select(ChatSession).where(ChatSession.id == chat_session_id)
        )
        chat_session = result.scalars().first()
        if chat_session:
            await self.session.delete(chat_session)
            return True
        return False
