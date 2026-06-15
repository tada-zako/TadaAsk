from typing import Sequence

from sqlalchemy import select, not_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatSession
from app.db.schemas import ChatSessionInternal
from app.core.constants import ChatSessionType


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

    async def list_chat_sessions_by_type(
        self,
        *,
        owner_type: ChatSessionType,
        limit: int = 10,
        offset: int = 0,
    ) -> Sequence[ChatSession]:
        """获取指定类型聊天会话列表"""
        result = await self.session.execute(
            select(ChatSession)
            .where(
                ChatSession.owner_type == owner_type,
                not_(ChatSession.is_archived),
            )
            .offset(offset)
            .limit(limit)
            .order_by(ChatSession.updated_at.desc())
        )
        return result.scalars().all()

    async def list_chat_sessions_by_type_and_project_id(
        self,
        *,
        project_id: int,
        owner_type: ChatSessionType,
        limit: int = 10,
        offset: int = 0,
    ) -> Sequence[ChatSession]:
        """获取指定类型聊天会话列表"""
        result = await self.session.execute(
            select(ChatSession)
            .where(
                ChatSession.owner_type == owner_type,
                ChatSession.project_id == project_id,
                not_(ChatSession.is_archived),
            )
            .offset(offset)
            .limit(limit)
            .order_by(ChatSession.updated_at.desc())
        )
        return result.scalars().all()

    async def get_chat_session_by_uid(
        self,
        *,
        project_id: int,
        chat_session_uid: str,
    ) -> ChatSession | None:
        """根据聊天会话 UID 获取聊天会话实例，如果未找到则返回 None"""
        result = await self.session.execute(
            select(ChatSession).where(
                ChatSession.uid == chat_session_uid,
                ChatSession.project_id == project_id,
            )
        )
        return result.scalars().first()

    async def update_chat_session_title(
        self, chat_session: ChatSession, new_title: str
    ) -> ChatSession:
        """更新聊天会话的标题"""
        chat_session.title = new_title
        await self.session.flush()  # 刷新以获取更新后的数据
        return chat_session

    async def update_chat_session_provider_and_model(
        self, chat_session: ChatSession, provider: str, model: str
    ) -> ChatSession:
        """更新聊天会话的 LLM 提供商和模型信息"""
        chat_session.provider = provider
        chat_session.model = model
        await self.session.flush()  # 刷新以获取更新后的数据
        return chat_session

    async def accumulate_tokens_usage(
        self,
        chat_session: ChatSession,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> ChatSession:
        """计算会话的 tokens 用量并更新"""
        chat_session.tokens_input += input_tokens
        chat_session.tokens_output += output_tokens
        chat_session.tokens_total += input_tokens + output_tokens
        await self.session.flush()  # 刷新以获取更新后的数据
        return chat_session

    async def archive_chat_session(self, chat_session: ChatSession) -> ChatSession:
        """将聊天会话标记为已归档（软删除）"""
        chat_session.is_archived = True
        await self.session.flush()  # 刷新以获取更新后的数据
        return chat_session

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
