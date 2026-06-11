from typing import AsyncIterable
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from .generation_registry import GenerationRegistry
from .context_builder import ContextBuilder
from ..rag import RAGRetrievalService
from ..schemas import (
    ChatStreamEvent,
    GenerationStartData,
    TextDeltaData,
    MessageDoneData,
    ErrorData,
)
from app.api.schemas import AdminChatRequest, VisitorChatRequest
from app.providers import Message, TextCompleter, StreamedResponse
from app.crud import ChatMessageCRUD, ChatSessionCRUD
from app.db.models import Project, ChatSession, ChatMessage, ModelProfile, Source
from app.db.schemas import HybridSearchOptions, ChatMessageRead
from app.core.constants import ChatMessageRole, ChatMessageType, ChatSessionType


class ChatOrchestratorService:
    """
    Chat 会话编排服务
    负责协调 ChatSession、TextCompleter、ContextBuilder 等组件，完成一次完整的 Chat 会话流程。
    包括但不限于：
    - 根据前端传递的 model_profile_uid 获取对应的 TextCompleter 实例
    - 验证或创建 ChatSession 实例
    - 调用 TextCompleter 生成回复内容
    - 调用 ContextBuilder 构建对话上下文
    - 处理对话中的各种事件（如消息开始、消息结束、错误等）
    """

    def __init__(
        self,
        *,
        session: AsyncSession,
        chat_message_crud: ChatMessageCRUD,
        chat_session_crud: ChatSessionCRUD,
        text_completer: TextCompleter,
        context_builder: ContextBuilder,
        rag_retrieval: RAGRetrievalService,
        generation_registry: GenerationRegistry,
    ):
        self.session = session
        self.chat_message_crud = chat_message_crud
        self.chat_session_crud = chat_session_crud
        self.text_completer = text_completer
        self.context_builder = context_builder
        self.rag_retrieval = rag_retrieval
        self.generation_registry = generation_registry

    async def stream_rag_chat(
        self,
        *,
        project: Project,
        sources: list[Source],
        request: AdminChatRequest | VisitorChatRequest,
        model_profile: ModelProfile,
        owner_type: ChatSessionType,
    ) -> AsyncIterable[ChatStreamEvent]:
        """流式对话；调用 RAG 服务"""

        # 1. 验证或创建 ChatSession
        chat_session = await self._valid_or_create_chat_session(
            project=project,
            request=request,
            owner_type=owner_type,
        )

        # 1.2 用户/Assistant 消息入库
        user_message = await self.chat_message_crud.append_message(
            chat_session_id=chat_session.id,
            message=request.message,
            role=ChatMessageRole.USER,
            type=ChatMessageType.MESSAGE,
            provider=model_profile.provider,
            model=model_profile.model,
        )

        assistant_message = await self.chat_message_crud.append_message(
            chat_session_id=chat_session.id,
            role=ChatMessageRole.ASSISTANT,
            message="",
            type=ChatMessageType.MESSAGE,
            provider=model_profile.provider,
            model=model_profile.model,
        )

        # 1.3 注册 generation 对象
        generation = self.generation_registry.register(
            session_uid=chat_session.uid,
            message_uid=user_message.uid,
        )

        # 1.4 yield 生成开始事件
        yield GenerationStartData(
            generation_uid=generation.generation_uid,
            session_uid=chat_session.uid,
            user_message=ChatMessageRead.model_validate(user_message),
            assistant_message=ChatMessageRead.model_validate(assistant_message),
        )

        # 2.0 预备参数
        assistant_buffer: list[str] = []

        try:
            # 2.1 获取最新的压缩消息
            compaction_message = (
                await self.chat_message_crud.get_lastest_compaction_message(
                    chat_session_id=chat_session.id
                )
            )

            # 2.2 获取最近消息
            recent_messages = await self._load_recent_messages(
                chat_session=chat_session,
                current_message_id=user_message.id,
                compaction_message=compaction_message,
            )

            # 2.3 构建 RAG 检索选项
            rag_options = self._resolve_rag_options(
                request=request,
                owner_type=owner_type,
                project=project,
                model_profile=model_profile,
            )

            # 2.4 调用 RAG 服务
            rag_result = await self.rag_retrieval.retrieve_for_chat(
                sources=sources,
                user_query=request.message,
                recent_messages=recent_messages,
                rag_options=rag_options,
            )

            # 2.5 构建对话上下文
            context = await self.context_builder.build_chat_context(
                project=project,
                compaction_message=compaction_message,
                recent_messages=recent_messages,
                current_message=user_message,
                rag_context=rag_result.context_block,
                model_profile=model_profile,
            )

            # 3 调用 TextCompleter 进行文本生成
            async with self.text_completer.stream_chat(context) as stream_response:
                async for chunk in stream_response:
                    # 3.0 处理生成的文本块
                    assistant_buffer.append(chunk)
                    delta = "".join(assistant_buffer)

                    # 3.1 监听生成取消事件
                    if generation.cancel_event.is_set():
                        await stream_response.cancel()

                        # 更新 Assistant 消息内容和 RAG 快照
                        if delta:
                            await self.chat_message_crud.update_assistant_message(
                                message_uid=assistant_message.uid,
                                new_message=delta,
                            )

                        yield TextDeltaData(
                            event="cancelled",
                            message_uid=assistant_message.uid,
                            delta=chunk,
                        )
                        return

                    # 3.2 正常生成中，持续更新 Assistant 消息内容
                    if delta:
                        await self.chat_message_crud.update_assistant_message(
                            message_uid=assistant_message.uid,
                            new_message=delta,
                        )
                    yield TextDeltaData(
                        event="delta",
                        message_uid=assistant_message.uid,
                        delta=chunk,
                    )

            # 4 生成完成，yield 消息完成事件
            yield MessageDoneData(
                message=ChatMessageRead.model_validate(assistant_message)
            )

        except asyncio.CancelledError:
            # 4.1 生成过程中被取消，yield 取消事件
            delta = "".join(assistant_buffer)
            await self.chat_message_crud.update_assistant_message(
                message_uid=assistant_message.uid,
                new_message=delta,
            )
            yield TextDeltaData(
                event="cancelled",
                message_uid=assistant_message.uid,
                delta="",
            )
            raise

        except Exception as e:
            # 4.2 生成过程中发生错误，yield 错误事件
            await self.session.rollback()  # 回滚数据库事务，避免脏数据
            yield ErrorData(
                message=str(e),
            )
            raise

        finally:
            # 5 清理注册的 generation 对象
            self.generation_registry.unregister(generation.generation_uid)
