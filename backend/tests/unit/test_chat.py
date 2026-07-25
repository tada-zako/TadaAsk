from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ChatMessageRole, ChatSessionType
from app.crud import ChatMessageCRUD, ChatSessionCRUD
from app.db.models import ChatMessage, ChatSession
from app.db.schemas import (
    ChatSessionInternal,
    ModelProfileRead,
    ProviderWithModelInternalRead,
    RAGSnapshot,
)
from app.providers import ModelSettings
from app.services.chat.chat_orchestrator import ChatInput, ChatOrchestratorService
from app.services.chat.compaction_service import CompactionService
from app.services.chat.context_builder import ContextBuilder
from app.services.chat.generation_registry import GenerationRegistry
from app.services.chat.session_operations import ChatSessionOpsService
from app.services.schemas import RAGRetrievalResult
from app.services.utils import TokenBudget
from tests.helpers import FakeCompleter, FakeTokenCounter


def provider_with_model() -> ProviderWithModelInternalRead:
    now = datetime.now(timezone.utc)
    profile = ModelProfileRead(
        uid="profile",
        model="fake-model",
        context_window_tokens=10_000,
        max_output_tokens=100,
        created_at=now,
        updated_at=now,
    )
    return ProviderWithModelInternalRead(
        uid="provider",
        name="fake",
        created_at=now,
        updated_at=now,
        model_profile=profile,
    )


async def collect_events(events) -> list[object]:
    return [event async for event in events]


@pytest.mark.asyncio
async def test_chat_stream_creates_then_continues_session_and_persists_message_order(
    session_factory,
) -> None:
    registry = GenerationRegistry()
    service = ChatOrchestratorService(
        session_factory=session_factory,
        context_builder=ContextBuilder(token_counter=FakeTokenCounter()),
        generation_registry=registry,
        compaction_service=CompactionService(session_factory, FakeTokenCounter()),
    )
    completer = FakeCompleter(chunks=["hello", " world"])
    settings = ModelSettings.for_compaction()

    events = await collect_events(
        service.stream_rag_chat(
            project=None,
            chat_input=ChatInput(message="first question", chat_session_uid=None),
            completer=completer,
            provider_with_model=provider_with_model(),
            requester_type=ChatSessionType.ADMIN,
            model_settings=settings,
            rag_plugin=None,
        )
    )
    session_ready = events[0]
    session_uid = session_ready.session.uid  # type: ignore[attr-defined]

    event_names = [event.event for event in events if hasattr(event, "event")]
    assert "error" not in event_names, events[-1]
    assert event_names == [
        "session_ready",
        "session_title_updated",
        "generation_start",
        "delta",
        "delta",
        "message_done",
    ]
    assert registry._registry == {}

    await collect_events(
        service.stream_rag_chat(
            project=None,
            chat_input=ChatInput(
                message="second question", chat_session_uid=session_uid
            ),
            completer=FakeCompleter(chunks=["second answer"]),
            provider_with_model=provider_with_model(),
            requester_type=ChatSessionType.ADMIN,
            model_settings=settings,
            rag_plugin=None,
        )
    )
    async with session_factory() as session:
        chat_session = await ChatSessionCRUD(session).get_chat_session_by_uid(
            chat_session_uid=session_uid
        )
        messages = await ChatMessageCRUD(session).list_messages_for_context(
            chat_session_id=chat_session.id
        )

    assert [
        (message.sequence, message.role, message.message) for message in messages
    ] == [
        (1, ChatMessageRole.USER, "first question"),
        (2, ChatMessageRole.ASSISTANT, "hello world"),
        (3, ChatMessageRole.USER, "second question"),
        (4, ChatMessageRole.ASSISTANT, "second answer"),
    ]


@pytest.mark.asyncio
async def test_rag_plugin_snapshot_is_emitted_before_text_and_persisted(
    session_factory,
) -> None:
    snapshot = RAGSnapshot(query="question")

    class RAGPluginStub:
        async def rag_retrieval_for_chat(self, **kwargs) -> RAGRetrievalResult:
            return RAGRetrievalResult(snapshot=snapshot, context_content="knowledge")

    service = ChatOrchestratorService(
        session_factory=session_factory,
        context_builder=ContextBuilder(token_counter=FakeTokenCounter()),
        generation_registry=GenerationRegistry(),
        compaction_service=CompactionService(session_factory, FakeTokenCounter()),
    )
    events = await collect_events(
        service.stream_rag_chat(
            project=None,
            chat_input=ChatInput(message="question", chat_session_uid=None),
            completer=FakeCompleter(chunks=["answer"]),
            provider_with_model=provider_with_model(),
            requester_type=ChatSessionType.ADMIN,
            model_settings=ModelSettings.for_compaction(),
            rag_plugin=RAGPluginStub(),
        )
    )

    names = [event.event for event in events if hasattr(event, "event")]
    assert names.index("rag_ready") < names.index("delta")
    done = events[-1]
    assert done.message.rag_snapshot.query == "question"  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_chat_stream_surfaces_provider_failure_and_handles_empty_output(
    session_factory,
) -> None:
    registry = GenerationRegistry()
    service = ChatOrchestratorService(
        session_factory=session_factory,
        context_builder=ContextBuilder(token_counter=FakeTokenCounter()),
        generation_registry=registry,
        compaction_service=CompactionService(session_factory, FakeTokenCounter()),
    )
    failed_events = await collect_events(
        service.stream_rag_chat(
            project=None,
            chat_input=ChatInput(message="fail", chat_session_uid=None),
            completer=FakeCompleter(error=RuntimeError("provider failed")),
            provider_with_model=provider_with_model(),
            requester_type=ChatSessionType.ADMIN,
            model_settings=ModelSettings.for_compaction(),
            rag_plugin=None,
        )
    )
    empty_completer = FakeCompleter()
    empty_completer.chunks = []
    empty_events = await collect_events(
        service.stream_rag_chat(
            project=None,
            chat_input=ChatInput(message="empty", chat_session_uid=None),
            completer=empty_completer,
            provider_with_model=provider_with_model(),
            requester_type=ChatSessionType.ADMIN,
            model_settings=ModelSettings.for_compaction(),
            rag_plugin=None,
        )
    )

    assert failed_events[-1].event == "error"  # type: ignore[attr-defined]
    assert failed_events[-1].message == "provider failed"  # type: ignore[attr-defined]
    assert empty_events[-1].event == "message_done"  # type: ignore[attr-defined]
    assert empty_events[-1].message.message == ""  # type: ignore[attr-defined]
    assert registry._registry == {}


@pytest.mark.asyncio
async def test_session_fork_preserves_snapshot_and_revert_removes_tail(
    db_session: AsyncSession,
) -> None:
    session_crud = ChatSessionCRUD(db_session)
    message_crud = ChatMessageCRUD(db_session)
    session = await session_crud.create_chat_session(
        chat_session_data=ChatSessionInternal(
            title="Original",
            owner_type=ChatSessionType.ADMIN,
            provider="fake",
            model="fake-model",
        )
    )
    first = await message_crud.append_message(
        chat_session_id=session.id,
        role=ChatMessageRole.USER,
        message="question",
        provider="fake",
        model="fake-model",
    )
    await message_crud.append_message(
        chat_session_id=session.id,
        role=ChatMessageRole.ASSISTANT,
        message="answer",
        provider="fake",
        model="fake-model",
        rag_snapshot=RAGSnapshot(query="question"),
    )
    ops = ChatSessionOpsService(
        chat_session_crud=session_crud,
        chat_message_crud=message_crud,
        generation_registry=GenerationRegistry(),
    )

    fork = await ops.fork_session(source_session=session, target_msg_sequence=2)
    copied = await message_crud.list_messages_for_context(chat_session_id=fork.id)
    deleted = await ops.revert_session(chat_session=session, message=first)

    assert fork.title == "Original (fork #1)"
    assert copied[1].rag_snapshot["query"] == "question"
    assert deleted == 2


def test_generation_registry_scope_cancel_and_context_priority() -> None:
    registry = GenerationRegistry()
    generation = registry.register(session_uid="session-a", message_uid="message")
    other_session = ChatSession(
        uid="session-b",
        title="other",
        owner_type=ChatSessionType.ADMIN,
        provider="p",
        model="m",
    )
    own_session = ChatSession(
        uid="session-a",
        title="own",
        owner_type=ChatSessionType.ADMIN,
        provider="p",
        model="m",
    )
    ops = ChatSessionOpsService(
        chat_session_crud=None,  # type: ignore[arg-type]
        chat_message_crud=None,  # type: ignore[arg-type]
        generation_registry=registry,
    )

    with pytest.raises(Exception, match="Generation not found"):
        ops.cancel_generation(
            chat_session=other_session, generation_uid=generation.generation_uid
        )
    assert ops.cancel_generation(
        chat_session=own_session, generation_uid=generation.generation_uid
    )
    assert registry.is_cancelled(generation.generation_uid)
    registry.unregister(generation.generation_uid)
    assert registry.get(generation.generation_uid) is None

    builder = ContextBuilder(token_counter=FakeTokenCounter())
    current = ChatMessage(
        sequence=4,
        role=ChatMessageRole.USER,
        message="current",
        provider="p",
        model="m",
        chat_session_id=1,
    )
    recent = [
        ChatMessage(
            sequence=1,
            role=ChatMessageRole.USER,
            message="old",
            provider="p",
            model="m",
            chat_session_id=1,
        ),
        ChatMessage(
            sequence=2,
            role=ChatMessageRole.ASSISTANT,
            message="recent",
            provider="p",
            model="m",
            chat_session_id=1,
        ),
    ]
    compact = ChatMessage(
        sequence=3,
        role=ChatMessageRole.SYSTEM,
        message="summary",
        provider="p",
        model="m",
        chat_session_id=1,
    )
    context = builder.build_chat_context(
        system_prompt="system",
        compaction_message=compact,
        recent_messages=recent,
        current_message=current,
        rag_context="knowledge exceeds the local budget",
        token_budget=TokenBudget(
            context_window_tokens=30, max_output_tokens=10, rag_context_ratio=0.3
        ),
    )

    assert context[0].content == "system"
    assert context[-1].content == "current"
    assert any("[Knowledge Context]" in message.content for message in context)
    assert all("summary" not in message.content for message in context)


def test_compaction_plan_preserves_tail_and_skips_short_history() -> None:
    service = CompactionService(session_factory=None, token_counter=FakeTokenCounter())  # type: ignore[arg-type]
    messages = [
        ChatMessage(
            sequence=1,
            role=ChatMessageRole.USER,
            message="12345",
            provider="p",
            model="m",
            chat_session_id=1,
        ),
        ChatMessage(
            sequence=2,
            role=ChatMessageRole.ASSISTANT,
            message="67890",
            provider="p",
            model="m",
            chat_session_id=1,
        ),
        ChatMessage(
            sequence=3,
            role=ChatMessageRole.USER,
            message="abcde",
            provider="p",
            model="m",
            chat_session_id=1,
        ),
    ]
    budget = TokenBudget(
        context_window_tokens=50, max_output_tokens=0, recent_tail_keep_ratio=0.2
    )

    plan = service.plan_compaction(recent_messages=messages, token_budget=budget)

    assert plan.need_compaction
    assert (plan.tail_start_sequence, plan.compact_until_sequence) == (2, 1)
    assert not service.plan_compaction(
        recent_messages=messages[:1], token_budget=budget
    ).need_compaction
