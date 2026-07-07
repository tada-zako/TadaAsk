from typing import AsyncIterable
import asyncio
from dataclasses import dataclass, field

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .generation_registry import GenerationRegistry
from .context_builder import ContextBuilder
from .compaction_service import CompactionService
from ..search import RAGRetrievalService, SearchSourceRef
from ..schemas import (
    ChatStreamEvent,
    SessionReadyData,
    SessionTitleUpdatedData,
    GenerationStartData,
    TextDeltaData,
    MessageDoneData,
    ErrorData,
    RAGRetrievalResult,
)
from ..utils import TokenBudget
from app.providers import (
    FullCompleter,
    TextCompleter,
    StructuredCompleter,
    StreamedResponse,
    ModelSettings,
    Message,
    DEFAULT_SYSTEM_PROMPT,
    TITLE_GENERATION_PROMPT,
)
from app.crud import ChatMessageCRUD, ChatSessionCRUD
from app.db.models import Project, ChatSession, ChatMessage, Source
from app.db.schemas import (
    HybridSearchOptions,
    ProviderWithModelInternalRead,
    ChatMessageRead,
    ChatSessionRead,
    ChatSessionInternal,
    RAGSnapshot,
)
from app.core.constants import (
    ChatMessageRole,
    ChatMessageType,
    ChatSessionType,
)


SESSION_TITLE_MAX_CHARS = 50
SESSION_TITLE_FALLBACK = "New chat"


@dataclass
class ChatInput:
    """封装 Chat 输入参数"""

    message: str
    chat_session_uid: str | None
    admin_system_prompt: str | None = None


@dataclass
class RAGChatPlugin:
    """RAG Chat 插件封装"""

    rag_retrieval: RAGRetrievalService
    rag_options: HybridSearchOptions
    source_refs: list[SearchSourceRef] = field(init=False)

    def __init__(
        self,
        sources: list[Source],
        rag_retrieval: RAGRetrievalService,
        rag_options: HybridSearchOptions,
    ) -> None:
        """将 ORM Source 转换为长流程安全的轻量引用"""
        self.rag_retrieval = rag_retrieval
        self.rag_options = rag_options
        self.source_refs = [
            SearchSourceRef(
                id=source.id,
                uid=source.uid,
                collection_name=source.collection_name,
                source_item_ids=[item.id for item in source.source_items],
            )
            for source in sources
        ]

    async def rag_retrieval_for_chat(
        self,
        *,
        user_query: str,
        recent_messages: list[ChatMessage],
        compaction_message: ChatMessage | None,
        completer: StructuredCompleter,
        token_budget: TokenBudget,
    ) -> RAGRetrievalResult:
        """封装 RAG 检索方法，供 ChatOrchestrator 调用"""
        return await self.rag_retrieval.retrieve_for_chat(
            sources=self.source_refs,
            user_query=user_query,
            recent_messages=recent_messages,
            compaction_message=compaction_message,
            completer=completer,
            token_budget=token_budget,
            rag_options=self.rag_options,
        )


class ChatOrchestratorService:
    """
    Chat 会话编排服务
    """

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        context_builder: ContextBuilder,
        generation_registry: GenerationRegistry,
        compaction_service: CompactionService,
    ):
        self.session_factory = session_factory
        self.context_builder = context_builder
        self.generation_registry = generation_registry
        self.compaction_service = compaction_service

    @staticmethod
    def _normalize_session_title(title: str | None) -> str | None:
        """清洗模型输出或用户输入中的会话标题。"""
        if not title:
            return None

        stripped_title = title.strip()
        first_line = (
            stripped_title.splitlines()[0]
            if stripped_title.splitlines()
            else stripped_title
        )
        normalized = " ".join(first_line.split())
        normalized = normalized.strip(" \t\r\n\"'`")
        if not normalized:
            return None

        # 按最大 title chars 截断
        return normalized[:SESSION_TITLE_MAX_CHARS]

    async def _valid_or_create_chat_session(
        self,
        *,
        project: Project | None,
        chat_input: ChatInput,
        provider: str,
        model: str,
        requester_type: ChatSessionType,
    ) -> tuple[ChatSession, bool]:
        """
        验证或创建 ChatSession 的内部方法
        - 验证前端传递的 chat_session_uid 是否有效，返回对应的 ChatSession 实例。
        - 如果 chat_session_uid 为空或无效，则创建新的 ChatSession 实例并返回。
        - 返回值包含 ChatSession 实例和一个布尔值，指示是否新创建了会话。
        """
        project_id = project.id if project else None
        if requester_type == ChatSessionType.VISITOR and project_id is None:
            # visitor 侧必须带有 project 上下文
            raise ValueError("Visitor chat requires project context")

        async with self.session_factory() as session:
            async with session.begin():
                chat_session_crud = ChatSessionCRUD(session=session)
                chat_session_uid = chat_input.chat_session_uid
                if chat_session_uid:
                    if requester_type == ChatSessionType.VISITOR:
                        # 查询 visitor session
                        assert project_id is not None
                        chat_session = (
                            await chat_session_crud.get_visitor_session_by_uid(
                                project_id=project_id,
                                chat_session_uid=chat_session_uid,
                            )
                        )
                    elif project_id is not None:
                        # 查询带 project 上下文的 admin session
                        chat_session = (
                            await chat_session_crud.get_admin_project_session_by_uid(
                                project_id=project_id,
                                chat_session_uid=chat_session_uid,
                            )
                        )
                    else:
                        # 查询 global 上下文 admin session
                        chat_session = (
                            await chat_session_crud.get_admin_global_session_by_uid(
                                chat_session_uid=chat_session_uid,
                            )
                        )

                    if not chat_session:
                        raise ValueError("Invalid chat_session_uid")

                    return chat_session, False

                # 创建新的 ChatSession
                new_chat_session = await chat_session_crud.create_chat_session(
                    chat_session_data=ChatSessionInternal(
                        title=SESSION_TITLE_FALLBACK,
                        owner_type=requester_type,
                        provider=provider,
                        model=model,
                        project_id=project_id,
                    )
                )
                await session.refresh(new_chat_session)
                return new_chat_session, True

    async def _append_initial_messages(
        self,
        *,
        chat_session_id: int,
        user_message_text: str,
        provider: str,
        model: str,
    ) -> tuple[ChatMessage, ChatMessage]:
        """短事务写入用户消息和 assistant placeholder"""
        async with self.session_factory() as session:
            async with session.begin():
                chat_message_crud = ChatMessageCRUD(session=session)
                user_message = await chat_message_crud.append_message(
                    chat_session_id=chat_session_id,
                    message=user_message_text,
                    role=ChatMessageRole.USER,
                    type=ChatMessageType.MESSAGE,
                    provider=provider,
                    model=model,
                )

                assistant_message = await chat_message_crud.append_message(
                    chat_session_id=chat_session_id,
                    role=ChatMessageRole.ASSISTANT,
                    message="",
                    type=ChatMessageType.MESSAGE,
                    provider=provider,
                    model=model,
                )

                await session.refresh(user_message)
                await session.refresh(assistant_message)
                return user_message, assistant_message

    async def _load_context_messages(
        self,
        *,
        chat_session_id: int,
        current_message: ChatMessage,
        compaction_message: ChatMessage | None = None,
    ) -> tuple[ChatMessage | None, list[ChatMessage]]:
        """短 session 加载 compaction 和 recent messages。"""
        async with self.session_factory() as session:
            chat_message_crud = ChatMessageCRUD(session=session)
            if compaction_message is None:
                compaction_message = (
                    await chat_message_crud.get_lastest_compaction_message(
                        chat_session_id=chat_session_id
                    )
                )

            recent_messages = list(
                await chat_message_crud.load_recent_messages(
                    chat_session_id=chat_session_id,
                    current_message=current_message,
                    compaction_message=compaction_message,
                )
            )
            return compaction_message, recent_messages

    async def _update_assistant_message(
        self,
        *,
        chat_session_id: int,
        assistant_message_id: int,
        new_message: str | None = None,
        new_rag_snapshot: RAGSnapshot | None = None,
    ) -> ChatMessageRead | None:
        """短事务更新 assistant 消息，并返回可直接下发的读取模型"""
        if new_message is None and new_rag_snapshot is None:
            # 都不传，干嘛调用...
            return None

        async with self.session_factory() as session:
            async with session.begin():
                chat_message_crud = ChatMessageCRUD(session=session)
                updated_message = (
                    await chat_message_crud.update_assistant_message_by_id(
                        chat_session_id=chat_session_id,
                        assistant_message_id=assistant_message_id,
                        new_message=new_message,
                        new_rag_snapshot=new_rag_snapshot,
                    )
                )
                if not updated_message:
                    raise ValueError("Assistant message not found")

                return ChatMessageRead.model_validate(updated_message)

    async def _generate_and_update_session_title(
        self,
        *,
        chat_session_id: int,
        user_message: str,
        completer: TextCompleter,
    ) -> ChatSessionRead | None:
        """为新会话生成标题并短事务更新；失败时返回 None，不影响主回答。"""
        try:
            # 非流式对话请求生成 title
            response = await completer.chat(
                messages=[
                    # 基础的 title gen context
                    Message(
                        role=ChatMessageRole.SYSTEM,
                        content=TITLE_GENERATION_PROMPT,
                    ),
                    Message(
                        role=ChatMessageRole.USER,
                        content=user_message,
                    ),
                ],
                model_settings=ModelSettings.for_title_generation(),
            )
            # 规范化 title
            generated_title = self._normalize_session_title(response.text)
            if not generated_title:
                return None

            async with self.session_factory() as session:
                async with session.begin():
                    # 打开 DB 短连接，更新 session title
                    chat_session_crud = ChatSessionCRUD(session=session)
                    updated_session = (
                        await chat_session_crud.update_chat_session_title_by_id(
                            chat_session_id=chat_session_id,
                            new_title=generated_title,
                        )
                    )
                    if not updated_session:
                        return None

                    return ChatSessionRead.model_validate(updated_session)
        except Exception as exc:
            logger.warning(f"Failed to generate chat session title: {exc}")
            return None

    def _resolve_system_prompt(
        self,
        *,
        project: Project | None,
        requester_type: ChatSessionType,
        chat_input: ChatInput,
    ) -> str:
        """解析 chat system prompt"""
        custom_prompt: str | None = None

        if project is not None:
            # project scoped chat 统一使用 project settings 中的 visitor prompt 作为附加提示词。
            project_settings = project.project_settings
            custom_prompt = (
                project_settings.visitor_system_prompt if project_settings else None
            )
        elif requester_type == ChatSessionType.ADMIN:
            # global admin chat 允许请求级附加 system prompt。
            custom_prompt = chat_input.admin_system_prompt

        if not custom_prompt or not custom_prompt.strip():
            return DEFAULT_SYSTEM_PROMPT

        return (
            DEFAULT_SYSTEM_PROMPT.rstrip()
            + "\n\n[Project/Admin Instructions]\n"
            + "Follow these additional instructions unless they conflict with the default instructions above.\n\n"
            + custom_prompt.strip()
            + "\n[/Project/Admin Instructions]"
        )

    async def _prepare_chat_context(
        self,
        *,
        chat_session: ChatSession,
        current_message: ChatMessage,
        system_prompt: str,
        completer: TextCompleter,
        provider: str,
        model: str,
        token_budget: TokenBudget,
    ) -> tuple[ChatMessage | None, list[ChatMessage]]:
        """
        预构建 Chat 上下文的内部方法

        内部判断是否需要主动 compact；
        如果需要，内部主动触发 compact 行为
        返回 (compaction_message | None, recent_messages)；
        """
        # 1. 获取最新的压缩消息和最近消息
        compaction_message, recent_messages = await self._load_context_messages(
            chat_session_id=chat_session.id,
            current_message=current_message,
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
                completer=completer,
                provider=provider,
                model=model,
                token_budget=token_budget,
            )

            compaction_message = new_compaction_message
            _, recent_messages = await self._load_context_messages(
                chat_session_id=chat_session.id,
                current_message=current_message,
                compaction_message=compaction_message,
            )

        return compaction_message, recent_messages

    async def stream_rag_chat(
        self,
        *,
        project: Project | None,
        chat_input: ChatInput,
        completer: FullCompleter,
        provider_with_model: ProviderWithModelInternalRead,
        requester_type: ChatSessionType,
        model_settings: ModelSettings,
        rag_plugin: RAGChatPlugin | None,
    ) -> AsyncIterable[ChatStreamEvent]:
        """流式对话；调用 RAG 服务"""

        # 0. 预备参数
        provider_name = provider_with_model.name
        model_name = provider_with_model.model_profile.model

        # 1. 验证或创建 ChatSession
        chat_session, session_created = await self._valid_or_create_chat_session(
            project=project,
            chat_input=chat_input,
            provider=provider_name,
            model=model_name,
            requester_type=requester_type,
        )

        # 1.1 yield 会话准备就绪事件
        yield SessionReadyData(
            session=ChatSessionRead.model_validate(chat_session),
            created=session_created,
        )

        # 1.2 用户/Assistant 消息入库
        user_message, assistant_message = await self._append_initial_messages(
            chat_session_id=chat_session.id,
            user_message_text=chat_input.message,
            provider=provider_name,
            model=model_name,
        )

        # 1.2.2 预备 system_prompt 以及 token_budget
        system_prompt = self._resolve_system_prompt(
            project=project,
            requester_type=requester_type,
            chat_input=chat_input,
        )
        token_budget = TokenBudget.from_model_profile(provider_with_model.model_profile)

        # 1.2.3 新会话标题生成
        if session_created:
            updated_session = await self._generate_and_update_session_title(
                chat_session_id=chat_session.id,
                user_message=chat_input.message,
                completer=completer,
            )
            if updated_session:
                # 失败时保留临时标题并继续主回答
                yield SessionTitleUpdatedData(session=updated_session)

        # 1.2.4 预备参数
        generation = None
        stream_response: StreamedResponse | None = None
        try:
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

            # 2.1 预构建对话上下文
            compaction_message, recent_messages = await self._prepare_chat_context(
                chat_session=chat_session,
                current_message=user_message,
                system_prompt=system_prompt,
                completer=completer,
                provider=provider_name,
                model=model_name,
                token_budget=token_budget,
            )

            rag_result: RAGRetrievalResult | None = None
            if rag_plugin:
                # 2.2 调用 RAG 服务
                rag_result = await rag_plugin.rag_retrieval_for_chat(
                    user_query=chat_input.message,
                    recent_messages=recent_messages,
                    compaction_message=compaction_message,
                    completer=completer,
                    token_budget=token_budget,
                )

                # 2.2.1 RAG 检索结果写库
                await self._update_assistant_message(
                    chat_session_id=chat_session.id,
                    assistant_message_id=assistant_message.id,
                    new_rag_snapshot=rag_result.snapshot,
                )

            # 2.3 构建对话上下文
            context = self.context_builder.build_chat_context(
                system_prompt=system_prompt,
                compaction_message=compaction_message,
                recent_messages=recent_messages,
                current_message=user_message,
                rag_context=rag_result.context_content if rag_result else None,
                token_budget=token_budget,
            )

            # 3. 调用 TextCompleter 进行文本生成
            async with completer.stream_chat(
                messages=context, model_settings=model_settings
            ) as response:
                stream_response = response

                async for chunk in stream_response:
                    # 3.1 监听生成取消事件
                    if generation.cancel_event.is_set():
                        await stream_response.cancel()

                        # 更新 Assistant 消息内容和 RAG 快照
                        final_message = stream_response.text
                        await self._update_assistant_message(
                            chat_session_id=chat_session.id,
                            assistant_message_id=assistant_message.id,
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
            updated_message = await self._update_assistant_message(
                chat_session_id=chat_session.id,
                assistant_message_id=assistant_message.id,
                new_message=final_message,
            )
            if updated_message:
                yield MessageDoneData(message=updated_message)

            # 4.0 TODO: 统计 token 用量，更新数据库中的消息记录

        except asyncio.CancelledError:
            # 4.1 生成过程中被取消
            final_message = stream_response.text if stream_response else ""
            if final_message:
                await self._update_assistant_message(
                    chat_session_id=chat_session.id,
                    assistant_message_id=assistant_message.id,
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
                await self._update_assistant_message(
                    chat_session_id=chat_session.id,
                    assistant_message_id=assistant_message.id,
                    new_message=final_message,
                )

            yield ErrorData(message=str(e))
            return

        finally:
            if generation is not None:
                # 5. 清理注册的 generation 对象
                self.generation_registry.unregister(generation.generation_uid)
