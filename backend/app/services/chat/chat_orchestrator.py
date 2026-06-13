from typing import AsyncIterable
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from .generation_registry import GenerationRegistry
from .context_builder import ContextBuilder
from .compaction_service import CompactionService
from ..rag import RAGRetrievalService
from ..schemas import (
    ChatStreamEvent,
    SessionReadyData,
    GenerationStartData,
    TextDeltaData,
    MessageDoneData,
    ErrorData,
)
from ..utils import TokenBudget
from app.api.schemas import AdminChatRequest, VisitorChatRequest
from app.providers import TextCompleter, StreamedResponse
from app.crud import ChatMessageCRUD, ChatSessionCRUD
from app.db.models import Project, ChatSession, ChatMessage, ModelProfile, Source
from app.db.schemas import (
    HybridSearchOptions,
    ChatMessageRead,
    ChatSessionRead,
    ChatSessionInternal,
)
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
        compaction_service: CompactionService,
    ):
        self.session = session
        self.chat_message_crud = chat_message_crud
        self.chat_session_crud = chat_session_crud
        self.text_completer = text_completer
        self.context_builder = context_builder
        self.rag_retrieval = rag_retrieval
        self.generation_registry = generation_registry
        self.compaction_service = compaction_service

    async def _valid_or_create_chat_session(
        self,
        *,
        project: Project,
        request: AdminChatRequest | VisitorChatRequest,
        model_profile: ModelProfile,
        requester_type: ChatSessionType,
    ) -> tuple[ChatSession, bool]:
        """
        验证或创建 ChatSession 的内部方法
        - 验证前端传递的 chat_session_uid 是否有效，返回对应的 ChatSession 实例。
        - 如果 chat_session_uid 为空或无效，则创建新的 ChatSession 实例并返回。
        - 返回值包含 ChatSession 实例和一个布尔值，指示是否新创建了会话。
        """
        chat_session_uid = request.chat_session_uid
        if chat_session_uid:
            chat_session = await self.chat_session_crud.get_chat_session_by_uid(
                chat_session_uid=chat_session_uid
            )
            if not chat_session:
                raise ValueError("Invalid chat_session_uid")

            # 会话权限限制：Admin 允许访问 admin/visitor 类型会话；
            # Visitor 仅允许访问 visitor 类型会话；如果不符合则抛出异常
            if (
                requester_type == ChatSessionType.VISITOR
                and chat_session.owner_type != ChatSessionType.VISITOR
            ):
                raise ValueError("Invalid chat_session_uid for visitor")

            return chat_session, False

        # 创建新的 ChatSession
        new_chat_session = await self.chat_session_crud.create_chat_session(
            chat_session_data=ChatSessionInternal(
                # TODO: 命名后续基于 LLM 响应结果动态更新
                title="",
                owner_type=requester_type,
                provider=model_profile.provider,
                model=model_profile.model,
                project_id=project.id,
            )
        )
        return new_chat_session, True

    async def _prepare_chat_context(
        self,
        *,
        chat_session: ChatSession,
        current_message: ChatMessage,
        system_prompt: str,
        text_completer: TextCompleter,
        model_profile: ModelProfile,
        token_budget: TokenBudget,
    ) -> tuple[ChatMessage | None, list[ChatMessage]]:
        """
        预构建 Chat 上下文的内部方法

        内部判断是否需要主动 compact；
        如果需要，内部主动触发 compact 行为
        返回 (compaction_message | None, recent_messages)；
        """
        # 1. 获取最新的压缩消息
        compaction_message = (
            await self.chat_message_crud.get_lastest_compaction_message(
                chat_session_id=chat_session.id
            )
        )

        # 2. 获取最近消息
        recent_messages = list(
            await self.chat_message_crud.load_recent_messages(
                chat_session_id=chat_session.id,
                current_message=current_message,
                compaction_message=compaction_message,
            )
        )

        # 3. 首先计算 compaction + recent + current 消息是否有可能会超出最大上下文限制
        need_compaction = self.compaction_service.estimate_without_rag(
            system_prompt=system_prompt,
            recent_messages=recent_messages,
            compaction_message=compaction_message,
            current_message=current_message,
            token_budget=token_budget,
        )

        # 4. 如果可能超出限制，需要先进行一次压缩，
        # 生成新的 compaction 消息，并更新数据库中的 compaction 消息记录；
        # 如果不可能超出限制，则继续使用现有的 compaction 消息记录
        if need_compaction:
            new_compaction_message = await self.compaction_service.compact(
                chat_session_id=chat_session.id,
                recent_messages=recent_messages,
                old_compaction_message=compaction_message,
                text_completer=text_completer,
                model_profile=model_profile,
                token_budget=token_budget,
            )

            # 确保数据库保持最新状态
            await self.session.flush()

            compaction_message = new_compaction_message
            recent_messages = list(
                await self.chat_message_crud.load_recent_messages(
                    chat_session_id=chat_session.id,
                    current_message=current_message,
                    compaction_message=compaction_message,
                )
            )

        return compaction_message, recent_messages

    async def stream_rag_chat(
        self,
        *,
        project: Project,
        sources: list[Source],
        request: AdminChatRequest | VisitorChatRequest,
        model_profile: ModelProfile,
        requester_type: ChatSessionType,
        rag_options: HybridSearchOptions,
    ) -> AsyncIterable[ChatStreamEvent]:
        """流式对话；调用 RAG 服务"""

        # 1. 验证或创建 ChatSession
        chat_session, session_created = await self._valid_or_create_chat_session(
            project=project,
            request=request,
            model_profile=model_profile,
            requester_type=requester_type,
        )

        # 1.1 yield 会话准备就绪事件
        yield SessionReadyData(
            session=ChatSessionRead.model_validate(chat_session),
            created=session_created,
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

        # 1.2.2 预备 system_prompt 以及 token_budget
        system_prompt = self._resolve_system_prompt()
        token_budget = TokenBudget.from_model_profile(model_profile)

        # 1.3 注册 generation 对象
        generation = self.generation_registry.register(
            session_uid=chat_session.uid,
            message_uid=assistant_message.uid,
        )

        # 1.4 yield 生成开始事件
        yield GenerationStartData(
            generation_uid=generation.generation_uid,
            session_uid=chat_session.uid,
            user_message=ChatMessageRead.model_validate(user_message),
            assistant_message=ChatMessageRead.model_validate(assistant_message),
        )

        # 2.0 预备参数
        stream_response: StreamedResponse | None = None

        try:
            # 2.1 预构建对话上下文
            compaction_message, recent_messages = await self._prepare_chat_context(
                chat_session=chat_session,
                current_message=user_message,
                system_prompt=system_prompt,
                text_completer=self.text_completer,
                model_profile=model_profile,
                token_budget=token_budget,
            )

            # 2.2 调用 RAG 服务
            rag_result = await self.rag_retrieval.retrieve_for_chat(
                sources=sources,
                user_query=request.message,
                recent_messages=recent_messages,
                compaction_message=compaction_message,
                rag_options=rag_options,
                token_budget=token_budget,
            )

            # 2.2.1 RAG 检索结果写库
            await self.chat_message_crud.update_assistant_message(
                assistant_message=assistant_message,
                new_rag_snapshot=rag_result.snapshot,
            )

            # 2.3 构建对话上下文
            context = self.context_builder.build_chat_context(
                system_prompt=system_prompt,
                compaction_message=compaction_message,
                recent_messages=recent_messages,
                current_message=user_message,
                rag_context=rag_result.context_content,
                token_budget=token_budget,
            )

            # 3. 调用 TextCompleter 进行文本生成
            async with self.text_completer.stream_chat(
                messages=context, model_settings=xx
            ) as response:
                stream_response = response

                async for chunk in stream_response:
                    # 3.1 监听生成取消事件
                    if generation.cancel_event.is_set():
                        await stream_response.cancel()

                        # 更新 Assistant 消息内容和 RAG 快照
                        final_message = stream_response.text
                        await self.chat_message_crud.update_assistant_message(
                            assistant_message=assistant_message,
                            new_message=final_message,
                        )

                        yield TextDeltaData(
                            event="cancelled",
                            message_uid=assistant_message.uid,
                            delta=chunk,
                        )
                        return

                    # 3.2 正常生成中；yield 文本增量事件
                    yield TextDeltaData(
                        event="delta",
                        message_uid=assistant_message.uid,
                        delta=chunk,
                    )

            # 4 生成完成；更新数据库并 yield 事件
            final_message = stream_response.text
            await self.chat_message_crud.update_assistant_message(
                assistant_message=assistant_message,
                new_message=final_message,
            )
            yield MessageDoneData(
                message=ChatMessageRead.model_validate(assistant_message)
            )

        except asyncio.CancelledError:
            # 4.1 生成过程中被取消
            final_message = stream_response.text if stream_response else ""
            if final_message:
                await self.chat_message_crud.update_assistant_message(
                    assistant_message=assistant_message,
                    new_message=final_message,
                )

            yield TextDeltaData(
                event="cancelled",
                message_uid=assistant_message.uid,
                delta="",
            )
            return

        except Exception as e:
            # 4.2 生成过程中发生错误
            final_message = stream_response.text if stream_response else ""

            if final_message:
                await self.chat_message_crud.update_assistant_message(
                    assistant_message=assistant_message,
                    new_message=final_message,
                )

            yield ErrorData(message=str(e))
            return

        finally:
            # 5. 清理注册的 generation 对象
            self.generation_registry.unregister(generation.generation_uid)
