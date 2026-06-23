import pytest

pytest.skip("legacy unit tests are outside the backend smoke-test scope", allow_module_level=True)

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from app.api.schemas import AdminChatRequest, VisitorChatRequest
from app.core.constants import ChatMessageRole
from app.db.schemas import ModelProfileRead
from app.providers import Message, ModelSettings, TokenUsage
from app.providers.gemini import GeminiModel, GeminiStreamedResponse
from app.providers.openai_compatible import OpenAIEndpoint
from app.services.chat.context_builder import ContextBuilder
from app.services.utils.token_budget import TokenBudget


def test_model_settings_from_profile_and_admin_request() -> None:
    profile = ModelProfileRead(
        uid="model-profile-uid",
        provider="google",
        model="gemini-2.5-flash",
        context_window_tokens=32768,
        max_output_tokens=2048,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    request = AdminChatRequest(
        message="hello",
        model_profile_uid="model-profile-uid",
        temperature=0.4,
        top_p=None,
        thinking="high",
    )

    settings = ModelSettings.from_profile_and_request(
        profile=profile,
        request=request,
        default_temperature=0.2,
        default_top_p=0.8,
        default_timeout=15,
        default_thinking="low",
    )

    assert settings.max_tokens == 2048
    assert settings.temperature == 0.4
    assert settings.top_p == 0.8
    assert settings.timeout == 15
    assert settings.thinking == "high"


def test_model_settings_from_profile_and_visitor_request_uses_defaults() -> None:
    profile = ModelProfileRead(
        uid="model-profile-uid",
        provider="google",
        model="gemini-2.5-flash",
        context_window_tokens=32768,
        max_output_tokens=2048,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    request = VisitorChatRequest(message="hello")

    settings = ModelSettings.from_profile_and_request(
        profile=profile,
        request=request,
        default_max_tokens=1024,
        default_temperature=0.1,
        default_top_p=0.6,
        default_timeout=20,
        default_thinking=False,
    )

    assert settings.max_tokens == 2048
    assert settings.temperature == 0.1
    assert settings.top_p == 0.6
    assert settings.timeout == 20
    assert settings.thinking is False


def test_token_usage_total_keeps_reasoning_separate_from_visible_output() -> None:
    usage = TokenUsage(input_tokens=10, output_tokens=20, reasoning_tokens=5)

    assert usage.total_tokens == 35


def test_gemini_maps_system_only_to_system_instruction() -> None:
    model = GeminiModel.__new__(GeminiModel)
    messages = [
        Message(role=ChatMessageRole.SYSTEM, content="main prompt"),
        Message(role=ChatMessageRole.USER, content="previous question"),
        Message(role=ChatMessageRole.ASSISTANT, content="previous answer"),
        Message(role=ChatMessageRole.SYSTEM, content="rag context"),
        Message(role=ChatMessageRole.USER, content="current question"),
    ]

    assert model._map_system_instruction(messages) == "main prompt\n\nrag context"

    contents = model._map_messages(messages)
    assert len(contents) == 3
    assert [content.role for content in contents] == ["user", "model", "user"]


def test_context_builder_maps_business_context_to_user_messages() -> None:
    class TokenCounterStub:
        def count_message(self, text: str) -> int:
            return len(text.split())

        def truncate_text(self, text: str, max_tokens: int) -> str:
            return text

    builder = ContextBuilder(token_counter=TokenCounterStub())
    messages = builder.build_chat_context(
        system_prompt="main prompt",
        compaction_message=SimpleNamespace(message="summary"),
        recent_messages=[],
        current_message=SimpleNamespace(
            role=ChatMessageRole.USER,
            message="current question",
        ),
        rag_context="retrieved facts",
        token_budget=TokenBudget(
            context_window_tokens=1000,
            max_output_tokens=100,
        ),
    )

    assert [message.role for message in messages] == [
        ChatMessageRole.SYSTEM,
        ChatMessageRole.USER,
        ChatMessageRole.USER,
        ChatMessageRole.USER,
    ]
    assert messages[1].content == (
        "[Conversation Summary]\nsummary\n[/Conversation Summary]"
    )
    assert messages[2].content == (
        "[Knowledge Context]\nretrieved facts\n[/Knowledge Context]"
    )


def test_gemini_process_response_maps_usage_and_preserves_raw_usage() -> None:
    model = GeminiModel.__new__(GeminiModel)
    raw_usage = SimpleNamespace(
        prompt_token_count=10,
        cached_content_token_count=3,
        thoughts_token_count=5,
        candidates_token_count=7,
    )
    response = SimpleNamespace(text="hello", usage_metadata=raw_usage)

    result = model._process_response(response)

    assert result.text == "hello"
    assert result.usage.input_tokens == 10
    assert result.usage.cache_read_tokens == 3
    assert result.usage.reasoning_tokens == 5
    assert result.usage.output_tokens == 7
    assert result.usage.raw_usage is raw_usage
    assert result.usage.total_tokens == 22


def test_gemini_streamed_response_buffers_text_and_usage() -> None:
    raw_usage = SimpleNamespace(
        prompt_token_count=10,
        cached_content_token_count=3,
        thoughts_token_count=5,
        candidates_token_count=7,
    )

    async def run() -> GeminiStreamedResponse:
        async def stream():
            yield SimpleNamespace(text="hel", usage_metadata=None)
            yield SimpleNamespace(text="lo", usage_metadata=raw_usage)

        response = GeminiStreamedResponse(response=stream())
        chunks = [chunk async for chunk in response]
        assert chunks == ["hel", "lo"]
        return response

    response = asyncio.run(run())

    assert response.text == "hello"
    assert response.usage.raw_usage is raw_usage
    assert response.get().text == "hello"
    assert response.get().state == "complete"


def test_openai_compatible_module_imports_without_self_import_cycle() -> None:
    endpoint = OpenAIEndpoint.deepseek()

    assert endpoint.endpoint_name == "deepseek"
