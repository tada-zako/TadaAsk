from datetime import datetime, timezone
import json
from types import SimpleNamespace

import httpx
import pytest
from openai import AsyncOpenAI, AuthenticationError
from pydantic import BaseModel

from app.core.constants import ChatMessageRole
from app.db.schemas import ModelProfileRead, ProviderWithModelInternalRead
from app.providers import Message, ModelSettings, completer_factory
from app.providers.adapters.anthropic import AnthropicModel
from app.providers.adapters.gemini import GeminiModel
from app.providers.adapters.openai_compatible.openai import OpenAIModel
from app.providers.adapters.openai_compatible.standard import (
    StandardOpenAICompatibleModel,
)
from app.services.model_profiles import ModelProfileService


pytestmark = pytest.mark.integration


def profile() -> ModelProfileRead:
    now = datetime.now(timezone.utc)
    return ModelProfileRead(
        uid="model",
        model="model-name",
        context_window_tokens=1000,
        max_output_tokens=123,
        created_at=now,
        updated_at=now,
    )


def provider(
    name: str, *, base_url: str | None = None
) -> ProviderWithModelInternalRead:
    now = datetime.now(timezone.utc)
    return ProviderWithModelInternalRead(
        uid="provider",
        name=name,
        base_url=base_url,
        api_key="test-key",
        created_at=now,
        updated_at=now,
        model_profile=profile(),
    )


def test_settings_factory_and_provider_factory_select_expected_adapters() -> None:
    admin = ModelSettings.for_admin_chat(profile=profile())
    visitor = ModelSettings.for_visitor_chat(
        profile=profile(),
        project_settings=SimpleNamespace(
            visitor_max_output_tokens=77,
            visitor_temperature=0.4,
            visitor_top_p=0.8,
            visitor_timeout=12.0,
            visitor_thinking=False,
        ),
    )

    assert admin.max_tokens == 123
    assert (visitor.max_tokens, visitor.temperature, visitor.timeout) == (77, 0.4, 12.0)
    assert isinstance(completer_factory(provider("openai")), OpenAIModel)
    assert isinstance(
        completer_factory(provider("custom", base_url="https://example.test/v1")),
        StandardOpenAICompatibleModel,
    )


@pytest.mark.asyncio
async def test_openai_compatible_mock_transport_maps_request_response_and_structured_output() -> (
    None
):
    requests: list[dict] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-1",
                "object": "chat.completion",
                "created": 1,
                "model": "test-model",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": '{"answer":"ok"}'},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 3,
                    "completion_tokens": 5,
                    "completion_tokens_details": {"reasoning_tokens": 2},
                },
            },
        )

    model = StandardOpenAICompatibleModel(
        model_perf="test-model",
        provider_name="custom",
        api_key="test-key",
        base_url="https://mock.test/v1",
    )
    model._client = AsyncOpenAI(
        api_key="test-key",
        base_url="https://mock.test/v1",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    settings = ModelSettings.for_compaction(max_tokens=20)
    try:
        response = await model.chat(
            messages=[
                Message(ChatMessageRole.SYSTEM, "rules"),
                Message(ChatMessageRole.USER, "hello"),
            ],
            model_settings=settings,
        )

        class Result(BaseModel):
            answer: str

        structured = await model.complete_structured(
            messages=[Message(ChatMessageRole.USER, "json")],
            model_settings=settings,
            schema=Result,
        )
    finally:
        await model._client.close()

    assert requests[0]["messages"] == [
        {"role": "system", "content": "rules"},
        {"role": "user", "content": "hello"},
    ]
    assert response.usage.output_tokens == 3
    assert structured.answer == "ok"


@pytest.mark.asyncio
async def test_openai_compatible_mock_transport_streams_usage_and_propagates_errors() -> (
    None
):
    stream_body = "\n\n".join(
        [
            'data: {"id":"chunk-1","object":"chat.completion.chunk","created":1,"model":"test-model","choices":[{"index":0,"delta":{"content":"hello"},"finish_reason":null}]}',
            'data: {"id":"chunk-2","object":"chat.completion.chunk","created":1,"model":"test-model","choices":[{"index":0,"delta":{"content":" world"},"finish_reason":"stop"}]}',
            'data: {"id":"chunk-3","object":"chat.completion.chunk","created":1,"model":"test-model","choices":[],"usage":{"prompt_tokens":7,"completion_tokens":5,"completion_tokens_details":{"reasoning_tokens":2}}}',
            "data: [DONE]",
            "",
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.headers.get("x-test-error"):
            return httpx.Response(
                401,
                json={"error": {"message": "bad key", "type": "invalid_request_error"}},
            )
        assert json.loads(request.content)["stream"] is True
        return httpx.Response(
            200, headers={"content-type": "text/event-stream"}, content=stream_body
        )

    model = StandardOpenAICompatibleModel(
        model_perf="test-model",
        provider_name="custom",
        api_key="test-key",
        base_url="https://mock.test/v1",
    )
    model._client = AsyncOpenAI(
        api_key="test-key",
        base_url="https://mock.test/v1",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    try:
        async with model.stream_chat(
            messages=[Message(ChatMessageRole.USER, "hello")],
            model_settings=ModelSettings.for_compaction(),
        ) as streamed:
            chunks = [chunk async for chunk in streamed]

        assert chunks == ["hello", " world"]
        assert streamed.get().usage.output_tokens == 3

        model._client = AsyncOpenAI(
            api_key="test-key",
            base_url="https://mock.test/v1",
            default_headers={"x-test-error": "1"},
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )
        with pytest.raises(AuthenticationError):
            await model.chat(
                messages=[Message(ChatMessageRole.USER, "hello")],
                model_settings=ModelSettings.for_compaction(),
            )
    finally:
        await model._client.close()


def test_anthropic_and_gemini_special_message_mappings() -> None:
    messages = [
        Message(ChatMessageRole.SYSTEM, "rules"),
        Message(ChatMessageRole.USER, "hello"),
    ]
    anthropic = AnthropicModel(model_perf="claude", api_key="key")
    system, mapped = anthropic._map_messages(messages)
    gemini = GeminiModel(model_perf="gemini", api_key="key")

    assert system == "rules"
    assert mapped == [{"role": "user", "content": "hello"}]
    assert gemini._map_system_instruction(messages) == "rules"
    assert gemini._map_messages(messages)[-1].role == "user"


@pytest.mark.asyncio
async def test_models_dev_catalog_fetch_uses_mock_transport(monkeypatch) -> None:
    payload = b'{"openai":{"models":{"gpt-test":{"id":"gpt-test","release_date":"2026-01-01"}}}}'
    original_async_client = httpx.AsyncClient

    def client_factory(**kwargs):
        return original_async_client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, content=payload)
            ),
            **kwargs,
        )

    monkeypatch.setattr("app.services.model_profiles.httpx.AsyncClient", client_factory)
    service = ModelProfileService(model_profile_crud=SimpleNamespace())

    catalog = await service._fetch_model_catalog(
        models_url="https://models.dev/api.json"
    )

    assert catalog["openai"].models["gpt-test"].id == "gpt-test"
