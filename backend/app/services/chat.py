# 1. 实例化 LLM 对象 / 单例模式
# 2. 基于 thread_id 获取上下文历史消息
# 3. 从 vector_db 获取相关文档内容
# 4. 构造 LLM 输入内容（系统提示词 + 历史消息 + 相关文档）
# 5. 调用 LLM 接口获取回复
# 6. 将用户消息和 AI 回复保存到数据库
from typing import Any, AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

# TODO: 使用 CRUD 层代码重构 Chat 服务层实现
from app.db.models import ChatSession, Project, Source
from app.db.schemas import ChatMessageInternal
from app.crud import chat_message_crud
from app.providers import Model, StreamedResponse
from app.context import build_history_context_window
from app.rag import VectorQueryItem
from app.services.rag import RAGService
from app.core.config import settings


class StreamedChatResult:
    """
    业务层流式对话结果封装：多保留一层封装中间件，方便未来扩展...
    """

    def __init__(self, raw_stream_response: StreamedResponse):
        self._raw_stream_response: StreamedResponse = raw_stream_response

    async def stream_reply(self) -> AsyncIterator[str]:
        total_reply = ""
        async for chunk in self._raw_stream_response:
            total_reply += chunk
            yield chunk

        self.response_content = total_reply


class ChatService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        llm_model: Model[Any],
        rag_service: RAGService,
    ):
        """
        Args:
            llm_model: Model 实例，提供构造消息和流式对话接口，通过外部 IoC 反向注入
            thread_service: ThreadService 实例，提供获取历史消息和相关文档等功能
        """
        self.session = session
        self.llm_model = llm_model
        self.rag_service = rag_service

    async def _build_context_window(
        self,
        chat_session_id: int,
    ) -> list[ChatMessageInternal]:
        """基于 chat_session_id 获取历史消息，并构建上下文窗口"""
        # 基于 CRUD 获取历史对话内容
        chat_history = await chat_message_crud.get_messages_by_session_id(
            self.session,
            chat_session_id=chat_session_id,
            limit=settings.sql_history_fetch_limit,
            offset=0,
        )

        # 构建历史对话上下文窗口
        context_window = build_history_context_window(
            chats=chat_history,
            max_context_tokens=settings.max_context_tokens,
            max_single_message_tokens=settings.max_single_message_tokens,
            model_name=self.llm_model.model_name,
        )
        logger.info(
            f"构建历史对话上下文窗口完成，原始消息数量={len(chat_history)}, "
            f"上下文窗口消息数量={len(context_window)}"
        )
        return context_window

    async def _rag_query(
        self, project_id: int, query_text: str, top_k: int
    ) -> list[VectorQueryItem]:
        """基于 project_id 获取关联的 sources，并进行 RAG 查询，返回相关文档列表"""
        related_docs = []
        # 基于 project 获取关联的 sources
        result = await self.session.execute(
            select(Source).where(Source.project_id == project_id)
        )
        sources = result.scalars().all()

        # 基于 sources 进行 RAG 操作
        if sources:
            logger.info(
                f"项目 ID {project_id} 关联的 sources 数量={len(sources)}，开始基于 sources 进行 RAG 操作"
            )
            for source in sources:
                source_related_docs = await self.rag_service.get_related_documents(
                    collection_uid=source.collection_name,
                    query_text=query_text,
                    top_k=top_k,
                )
                related_docs.extend(source_related_docs)

        # TODO: 对于多集合查询的结果进行 rerank，现在只简单的提取前 top_k 个相关文档
        related_docs = related_docs[:top_k]
        logger.info(
            f"RAG 查询完成，相关文档数量={len(related_docs)}，"
            f"相关文档标题列表={[doc.metadata.get('title', '') for doc in related_docs]}"
        )

        return related_docs

    # TODO: 未来需要重构这里的业务逻辑，不由外部直接提供 collection_uid 来决定 RAG 检索的内容
    @asynccontextmanager
    async def stream_chat_reply(
        self,
        *,
        project: Project,  # 业务中可能会需要基于 project 获取相关资源
        chat_session: ChatSession,  # 业务层认为 chat_session 确实存在
        user_message: str,
        top_k: int = 5,
    ) -> AsyncIterator[StreamedChatResult]:
        """
        基于 GeminiModel 的流式对话接口，获取 AI 回复内容

        Args:
            thread_uid: 对话线程 UID，用于获取历史消息和相关文档
            collection_uid: 向量集合 UID，用于向量库查询相关文档（可选）
            user_message: 用户输入的消息内容
            session: 数据库会话，由外部注入
            top_k: 向量库查询返回的相关文档数量，默认为 5

        Returns:
            AsyncGenerator，逐步返回 LLM 生成的回复内容
        """
        # 构建历史对话上下文窗口
        context_window = await self._build_context_window(
            chat_session_id=chat_session.id
        )

        # 向量库查询
        related_docs = await self._rag_query(
            project_id=project.id, query_text=user_message, top_k=top_k
        )

        # 用户消息入库
        await chat_message_crud.save_chat_to_db(
            self.session,
            role="user",
            message=user_message,
            chat_session_id=chat_session.id,
        )

        # 构造 LLM 输入消息
        messages = self.llm_model.construct_messages(
            document=related_docs,
            user_message=user_message,
            chat_history=context_window,
        )

        # 获取流式回复内容
        logger.info(
            f"开始调用 LLM 流式对话接口，等待回复生成...，"
            f"输入消息长度={len(user_message)}, "
            f"历史消息数量={len(context_window)}, "
            f"相关文档数量={len(related_docs)}"
        )

        async with self.llm_model.stream_chat(messages) as stream_response:
            # 业务层不直接迭代 yield LLM 的流式响应内容，而是封装一层 StreamedChatResult，方便未来扩展
            chat_result = StreamedChatResult(stream_response)
            yield chat_result
            # TODO: 基于 Sonnet 的说明，目前对于 LLM 流式输出的实现，可能会导致问题：
            # 当客户端过早断开流式输出的连接， AI 回复的内容可能不完整或者丢失，
            # 导致 SQL 中保存的 AI 回复内容不完整。
            logger.info(
                f"LLM 回复生成完成，回复内容长度={len(chat_result.response_content)}"
            )

            # 保存 AI 回复
            await chat_message_crud.save_chat_to_db(
                self.session,
                role="assistant",
                message=chat_result.response_content,
                chat_session_id=chat_session.id,
                citation=None,  # TODO: 未来可以基于 RAG 查询结果构建引用信息
            )
