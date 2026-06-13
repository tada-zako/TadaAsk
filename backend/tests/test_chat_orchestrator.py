from contextlib import asynccontextmanager
import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from app.core.constants import ChatMessageRole, ChatMessageType, ChatSessionType
from app.db.schemas import HybridSearchOptions, RAGSnapshot
from app.providers import DEFAULT_SYSTEM_PROMPT
from app.services.chat.chat_orchestrator import ChatOrchestratorService
from app.services.chat.compaction_service import CompactionService
from app.services.chat.generation_registry import GenerationRegistry
from app.services.rag.retrieval import RAGRetrievalService
from app.services.schemas import RAGRetrievalResult
from app.services.utils import TokenBudget


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _session(**overrides):
    data = {
        "id": 1,
        "uid": "session-uid",
        "title": "",
        "owner_type": ChatSessionType.VISITOR,
        "provider": "test",
        "model": "model",
        "created_at": _now(),
        "updated_at": _now(),
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _message(**overrides):
    data = {
        "id": 1,
        "uid": "message-uid",
        "sequence": 1,
        "role": ChatMessageRole.USER,
        "message": "hello",
        "type": ChatMessageType.MESSAGE,
        "tail_start_sequence": None,
        "provider": "test",
        "model": "model",
        "rag_snapshot": None,
        "created_at": _now(),
    }
    data.update(overrides)
    return SimpleNamespace(**data)


class FakeDBSession:
    def __init__(self):
        self.flush_count = 0

    async def flush(self):
        self.flush_count += 1


class FakeChatSessionCRUD:
    def __init__(self):
        self.created_session = _session()

    async def get_chat_session_by_uid(self, *, chat_session_uid: str):
        return None

    async def create_chat_session(self, *, chat_session_data):
        self.created_session = _session(
            owner_type=chat_session_data.owner_type,
            provider=chat_session_data.provider,
            model=chat_session_data.model,
        )
        return self.created_session


class FakeChatMessageCRUD:
    def __init__(self):
        self.messages = []

    async def append_message(
        self,
        *,
        chat_session_id: int,
        role: ChatMessageRole,
        message: str,
        type: ChatMessageType,
        provider: str,
        model: str,
        tail_start_sequence: int | None = None,
        rag_snapshot=None,
    ):
        msg = _message(
            id=len(self.messages) + 1,
            uid=f"message-{len(self.messages) + 1}",
            sequence=len(self.messages) + 1,
            role=role,
            message=message,
            type=type,
            provider=provider,
            model=model,
            tail_start_sequence=tail_start_sequence,
            rag_snapshot=rag_snapshot,
        )
        self.messages.append(msg)
        return msg

    async def get_lastest_compaction_message(self, *, chat_session_id: int):
        return None

    async def load_recent_messages(self, *, chat_session_id, current_message, compaction_message=None):
        return []

    async def update_assistant_message(
        self,
        *,
        assistant_message,
        new_message: str | None = None,
        new_rag_snapshot=None,
    ):
        if new_message is not None:
            assistant_message.message = new_message
        if new_rag_snapshot is not None:
            assistant_message.rag_snapshot = new_rag_snapshot.model_dump()
        return assistant_message


class FakeContextBuilder:
    def __init__(self):
        self.calls = []

    def build_chat_context(self, **kwargs):
        self.calls.append(kwargs)
        return []


class FakeRAGRetrieval:
    async def retrieve_for_chat(self, *, user_query: str, **kwargs):
        return RAGRetrievalResult(
            snapshot=RAGSnapshot(query=user_query),
            context_block=None,
        )


class FakeHybridSearchService:
    async def search(self, **kwargs):
        return []


class FakeCompactionService:
    def estimate_without_rag(self, **kwargs):
        return False


class FakeStream:
    def __init__(self, chunks):
        self.chunks = chunks
        self.cancelled = False

    def __aiter__(self):
        return self._iter()

    async def _iter(self):
        for chunk in self.chunks:
            yield chunk

    async def cancel(self):
        self.cancelled = True


class FakeCompleter:
    def __init__(self, chunks):
        self.chunks = chunks
        self.streamed_messages = []

    @property
    def model_name(self) -> str:
        return "model"

    @asynccontextmanager
    async def stream_chat(self, messages):
        self.streamed_messages.append(messages)
        yield FakeStream(self.chunks)


def _model_profile(**overrides):
    data = {
        "provider": "test",
        "model": "model",
        "context_window_tokens": 100,
        "max_output_tokens": 20,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _orchestrator(*, context_builder=None, completer=None):
    return ChatOrchestratorService(
        session=FakeDBSession(),
        chat_message_crud=FakeChatMessageCRUD(),
        chat_session_crud=FakeChatSessionCRUD(),
        text_completer=completer or FakeCompleter(["hel", "lo"]),
        context_builder=context_builder or FakeContextBuilder(),
        rag_retrieval=FakeRAGRetrieval(),
        generation_registry=GenerationRegistry(),
        compaction_service=FakeCompactionService(),
    )


def _run(coro):
    return asyncio.run(coro)


async def _collect_chat_events(service, *, project, request, requester_type):
    return [
        event
        async for event in service.stream_rag_chat(
            project=project,
            sources=[],
            request=request,
            model_profile=_model_profile(),
            requester_type=requester_type,
            rag_options=HybridSearchOptions(),
        )
    ]


def test_stream_rag_chat_runs_normal_flow_and_persists_final_message():
    async def run_test():
        service = _orchestrator()
        request = SimpleNamespace(message="hello", chat_session_uid=None)
        project = SimpleNamespace(id=1, chat_setting=None)

        events = await _collect_chat_events(
            service,
            project=project,
            request=request,
            requester_type=ChatSessionType.ADMIN,
        )

        assert [event.event for event in events] == [
            "session_ready",
            "generation_start",
            "delta",
            "delta",
            "message_done",
        ]
        assert events[-1].message.message == "hello"
        assert service.chat_message_crud.messages[-1].message == "hello"
        assert service.generation_registry._registry == {}

    _run(run_test())


def test_stream_rag_chat_uses_visitor_project_system_prompt():
    async def run_test():
        context_builder = FakeContextBuilder()
        service = _orchestrator(context_builder=context_builder)
        request = SimpleNamespace(message="hello", chat_session_uid=None)
        project = SimpleNamespace(
            id=1,
            chat_setting=SimpleNamespace(visitor_system_prompt="visitor prompt"),
        )

        await _collect_chat_events(
            service,
            project=project,
            request=request,
            requester_type=ChatSessionType.VISITOR,
        )

        assert context_builder.calls[0]["system_prompt"] == "visitor prompt"

    _run(run_test())


def test_stream_rag_chat_falls_back_to_default_system_prompt_for_blank_visitor_prompt():
    async def run_test():
        context_builder = FakeContextBuilder()
        service = _orchestrator(context_builder=context_builder)
        request = SimpleNamespace(message="hello", chat_session_uid=None)
        project = SimpleNamespace(
            id=1,
            chat_setting=SimpleNamespace(visitor_system_prompt=" "),
        )

        await _collect_chat_events(
            service,
            project=project,
            request=request,
            requester_type=ChatSessionType.VISITOR,
        )

        assert context_builder.calls[0]["system_prompt"] == DEFAULT_SYSTEM_PROMPT

    _run(run_test())


def test_compaction_keeps_tail_boundary_and_uses_streaming_completer():
    async def run_test():
        message_crud = FakeCompactionMessageCRUD()
        service = CompactionService(
            chat_message_crud=message_crud,
            chat_session_crud=SimpleNamespace(),
            text_completer=FakeCompleter(["summary"]),
            token_counter=FakeTokenCounter(),
        )
        recent_messages = [
            _message(sequence=1, message="10"),
            _message(sequence=2, message="10"),
            _message(sequence=3, message="10"),
        ]

        result = await service.compact(
            chat_session_id=1,
            system_prompt="system",
            recent_messages=recent_messages,
            old_compaction_message=None,
            text_completer=FakeCompleter(["summary"]),
            model_profile=_model_profile(),
            token_budget=TokenBudget(context_window_tokens=100, max_output_tokens=0),
        )

        assert result.message == "summary"
        assert result.tail_start_sequence == 2
        assert message_crud.append_calls[0]["tail_start_sequence"] == 2

    _run(run_test())


def test_rag_retrieval_returns_no_context_block_when_search_has_no_hits():
    async def run_test():
        service = RAGRetrievalService(
            rag_search_crud=SimpleNamespace(),
            hybrid_search_service=FakeHybridSearchService(),
            standalone_rewriter=SimpleNamespace(),
            token_counter=SimpleNamespace(),
        )

        result = await service.retrieve_for_chat(
            sources=[],
            user_query="question",
            recent_messages=[],
            compaction_message=None,
            rag_options=HybridSearchOptions(),
            token_budget=TokenBudget(context_window_tokens=100, max_output_tokens=0),
        )

        assert result.context_block is None

    _run(run_test())


class FakeTokenCounter:
    def count_message(self, message: str) -> int:
        return int(message)


class FakeCompactionMessageCRUD:
    def __init__(self):
        self.append_calls = []

    async def append_message(self, **kwargs):
        self.append_calls.append(kwargs)
        return _message(
            role=kwargs["role"],
            message=kwargs["message"],
            type=kwargs["type"],
            tail_start_sequence=kwargs["tail_start_sequence"],
        )

