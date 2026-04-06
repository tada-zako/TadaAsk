# 1. 实例化 LLM 对象 / 单例模式
# 2. 基于 thread_id 获取上下文历史消息
# 3. 从 vector_db 获取相关文档内容
# 4. 构造 LLM 输入内容（系统提示词 + 历史消息 + 相关文档）
# 5. 调用 LLM 接口获取回复
# 6. 将用户消息和 AI 回复保存到数据库
from typing import AsyncGenerator, Any

from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.services.chat_thread import ChatThreadService
from app.services.rag import RAGService
from app.ai_engine import LLModel


class ChatService:
    def __init__(
        self,
        llm_model: LLModel[Any] | None = None,
        thread_service: ChatThreadService | None = None,
        rag_service: RAGService | None = None,
    ):
        """
        Args:
            llm_model: LLModel 实例，提供构造消息和流式对话接口，通过外部 IoC 反向注入
            thread_service: ChatThreadService 实例，提供获取历史消息和相关文档等功能
        """
        if llm_model is None:
            raise ValueError(
                "llm_model must be provided by external dependency injection"
            )
        if thread_service is None:
            raise ValueError(
                "thread_service must be provided by external dependency injection"
            )
        if rag_service is None:
            raise ValueError(
                "rag_service must be provided by external dependency injection"
            )

        self.llm_model = llm_model
        self.thread_service = thread_service
        self.rag_service = rag_service

    async def stream_chat_reply(
        self,
        session: AsyncSession,
        *,
        thread_uid: str,
        user_message: str,
        collection_uid: str | None = None,
        top_k: int = 5,
    ) -> AsyncGenerator[str, None]:
        """
        基于 GeminiLLM 的流式对话接口，获取 AI 回复内容

        Args:
            thread_uid: 对话线程 UID，用于获取历史消息和相关文档
            collection_uid: 向量集合 UID，用于向量库查询相关文档（可选）
            user_message: 用户输入的消息内容
            session: 数据库会话，由外部注入
            top_k: 向量库查询返回的相关文档数量，默认为 5

        Returns:
            AsyncGenerator，逐步返回 LLM 生成的回复内容
        """
        # 统一解析 thread_uid，获取 thread_id 与历史消息
        (
            thread_id,
            chat_history,
        ) = await self.thread_service.resolve_thread_context_by_uid(session, thread_uid)

        # 向量库查询
        related_docs = []
        if collection_uid:
            logger.info(
                f"开始向量库查询，thread_uid={thread_uid}, collection_uid={collection_uid}, query_text='{user_message[:50]}', top_k={top_k}"
            )
            related_docs = await self.rag_service.get_related_documents(
                session,
                collection_uid=collection_uid,
                query_text=user_message,
                top_k=top_k,
            )

        # 用户消息入库
        await self.thread_service.save_chat_to_db(
            session,
            thread_id=thread_id,
            role="user",
            message=user_message,
        )

        # 构造 LLM 输入消息
        messages = self.llm_model.construct_messages(
            document=related_docs,
            user_message=user_message,
            chat_history=chat_history,
        )

        # 获取流式回复内容
        logger.info(
            f"开始调用 LLM 实例流式回复，用户消息长度={len(user_message)}, 历史消息轮数={len(chat_history) // 2}, 相关文档数量={len(related_docs)}"
        )
        chunks: list[str] = []
        async for chunk in self.llm_model.stream_chat(messages):
            chunks.append(chunk)
            yield chunk
        reply_content = "".join(chunks)

        logger.info(f"LLM 回复生成完成，回复内容长度={len(reply_content)}")

        # 保存 AI 回复
        await self.thread_service.save_chat_to_db(
            session, thread_id=thread_id, role="assistant", message=reply_content
        )
