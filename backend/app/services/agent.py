from typing import AsyncIterator, Literal

from pydantic_ai import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    UserPromptPart,
    TextPart,
)
from pydantic_ai.models import Model as AgentModel
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.ai_engine.agent import AgentExecutorRegistry, AgentDeps
from app.services.chat_thread import ChatThreadService
from app.services.rag import RAGService


class AgentService:
    def __init__(
        self,
        context_provider: ChatThreadService | None = None,
        rag_provider: RAGService | None = None,
        llm_model: AgentModel | None = None,
    ) -> None:
        if context_provider is None:
            raise ValueError(
                "context_provider must be provided by external dependency injection"
            )
        if rag_provider is None:
            raise ValueError(
                "rag_provider must be provided by external dependency injection"
            )
        if llm_model is None:
            raise ValueError(
                "llm_model must be provided by external dependency injection"
            )

        self.context_provider = context_provider
        self.rag_provider = rag_provider
        self.llm_model = llm_model

    async def run_agent(
        self,
        session: AsyncSession,
        *,
        thread_uid: str,
        user_message: str,
        collection_uid: str | None = None,
        mode: Literal["rag_search", "web_search"],
    ) -> AsyncIterator[str]:
        # 统一解析 thread_uid，获取 thread_id 与历史消息
        (
            thread_id,
            chat_history,
        ) = await self.context_provider.resolve_thread_context_by_uid(
            session, thread_uid
        )

        # 存储当前轮用户消息（历史重建后保存，避免当前输入重复进入 message_history）
        await self.context_provider.save_chat_to_db(
            session, thread_id=thread_id, role="user", message=user_message
        )

        # 重建 Agent 对话历史
        logger.info(f"重建 Agent 对话历史，历史消息数量：{len(chat_history)}")
        messages: list[ModelMessage] = []
        for entry in chat_history:
            # NOTE: DEMO 只保留了用户请求和 AI 回复的文本内容，
            # 舍弃了包括 Tool 调用在内的其他消息类型和结构。
            if entry.role == "user":
                messages.append(
                    ModelRequest(
                        parts=[UserPromptPart(content=entry.message)],
                        timestamp=entry.created_at,
                    )
                )
            else:
                messages.append(
                    ModelResponse(
                        parts=[TextPart(content=entry.message)],
                        timestamp=entry.created_at,
                    )
                )

        # 流式执行 Agent 对话
        logger.info(
            f"开始流式执行 Agent 对话，用户输入长度：{len(user_message)}，历史消息轮数：{len(chat_history) // 2}"
        )

        agent_executor = AgentExecutorRegistry.get_executor(mode)

        async with agent_executor.run(
            user_message,
            deps=AgentDeps(
                db_session=session,
                context_provider=self.context_provider,
                rag_provider=self.rag_provider,
                thread_uid=thread_uid,
                collection_uid=collection_uid,
            ),
            message_history=messages,
            model=self.llm_model,
        ) as response:
            async for chunk in response.text_chunks():
                yield chunk

            reply_content = await response.full_text()

        logger.info(f"Agent 对话执行完成，回复内容长度：{len(reply_content)}")
        # 存储 AI 回复到数据库
        await self.context_provider.save_chat_to_db(
            session, thread_id=thread_id, role="assistant", message=reply_content
        )
