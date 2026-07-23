"""Anthropic Messages API 适配器。"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, TypeVar

from anthropic import AsyncAnthropic
from pydantic import BaseModel

from app.core.constants import ChatMessageRole

from ..base import Message, ModelResponse, ModelSettings, StreamedResponse, TokenUsage


T = TypeVar("T", bound=BaseModel)


class AnthropicStreamedResponse(StreamedResponse):
    """将 Anthropic 原始 SSE 事件转换为 TadaAsk 文本流。"""

    def __init__(self, stream_iter: Any):
        super().__init__()
        self.stream_iter = stream_iter

    def _update_usage(self, raw_usage: Any) -> None:
        details = getattr(raw_usage, "output_tokens_details", None)
        self._usage = TokenUsage(
            input_tokens=getattr(raw_usage, "input_tokens", 0) or 0,
            cache_write_tokens=getattr(raw_usage, "cache_creation_input_tokens", 0)
            or 0,
            cache_read_tokens=getattr(raw_usage, "cache_read_input_tokens", 0)
            or 0,
            output_tokens=getattr(raw_usage, "output_tokens", 0) or 0,
            reasoning_tokens=getattr(details, "thinking_tokens", 0) or 0,
            raw_usage=raw_usage,
        )

    async def _get_stream_iter(self) -> AsyncIterator[str]:
        async for event in self.stream_iter:
            if event.type == "message_start":
                self._update_usage(event.message.usage)
                continue

            if event.type == "message_delta":
                self._update_usage(event.usage)
                continue

            if (
                event.type == "content_block_delta"
                and event.delta.type == "text_delta"
            ):
                text = event.delta.text
                self._text_buffer.append(text)
                yield text

    async def close_stream(self) -> None:
        await self.stream_iter.close()


class AnthropicModel:
    """Anthropic Messages API 的统一文本与结构化输出实现。"""

    def __init__(
        self,
        *,
        model_perf: str,
        api_key: str,
        base_url: str | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("Anthropic API key is required.")

        self._model = model_perf
        self._client = AsyncAnthropic(api_key=api_key, base_url=base_url)

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def provider_name(self) -> str:
        return "anthropic"

    def _map_messages(self, messages: list[Message]) -> tuple[str | None, list[dict[str, str]]]:
        """Anthropic 将 system prompt 放在顶层字段，其他角色保持原有顺序。"""
        system_messages: list[str] = []
        anthropic_messages: list[dict[str, str]] = []

        for message in messages:
            if message.role == ChatMessageRole.SYSTEM:
                system_messages.append(message.content)
                continue

            role = "assistant" if message.role == ChatMessageRole.ASSISTANT else "user"
            anthropic_messages.append({"role": role, "content": message.content})

        if not anthropic_messages:
            raise ValueError("Anthropic requests require at least one user message.")

        system = "\n\n".join(system_messages).strip()
        return (system or None), anthropic_messages

    def _request_kwargs(
        self,
        *,
        messages: list[Message],
        model_settings: ModelSettings,
        output_format: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        system, anthropic_messages = self._map_messages(messages)
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": model_settings.max_tokens,
            "messages": anthropic_messages,
            "timeout": model_settings.timeout,
        }
        if system:
            kwargs["system"] = system

        thinking = self._thinking_config(model_settings.thinking)
        if thinking is not None:
            kwargs["thinking"] = thinking
        else:
            kwargs["temperature"] = model_settings.temperature
            kwargs["top_p"] = model_settings.top_p

        output_config: dict[str, Any] = {}
        effort = self._translate_effort(model_settings.thinking)
        if effort is not None:
            output_config["effort"] = effort
        if output_format is not None:
            output_config["format"] = output_format
        if output_config:
            kwargs["output_config"] = output_config
        return kwargs

    def _translate_effort(self, thinking: bool | str) -> str | None:
        if thinking is False:
            return None
        if thinking is True:
            return "high"
        if thinking == "minimal":
            return "low"
        return thinking

    def _thinking_config(self, thinking: bool | str) -> dict[str, str] | None:
        """只在模型支持的情况下传入 adaptive/disabled thinking 配置。"""
        model = self._model.lower()
        always_on = model.startswith(("claude-fable-5", "claude-mythos"))
        if always_on:
            return None
        if thinking is False:
            return {"type": "disabled"}

        adaptive_models = (
            "claude-opus-4-6",
            "claude-opus-4-7",
            "claude-opus-4-8",
            "claude-sonnet-4-6",
            "claude-sonnet-5",
        )
        if model.startswith(adaptive_models):
            return {"type": "adaptive"}
        return None

    @staticmethod
    def _to_model_response(response: Any) -> ModelResponse:
        content = "".join(
            block.text for block in response.content if block.type == "text"
        )
        usage = response.usage
        details = getattr(usage, "output_tokens_details", None)
        return ModelResponse(
            text=content,
            usage=TokenUsage(
                input_tokens=usage.input_tokens or 0,
                cache_write_tokens=usage.cache_creation_input_tokens or 0,
                cache_read_tokens=usage.cache_read_input_tokens or 0,
                output_tokens=usage.output_tokens or 0,
                reasoning_tokens=getattr(details, "thinking_tokens", 0) or 0,
                raw_usage=usage,
            ),
        )

    async def chat(
        self,
        *,
        messages: list[Message],
        model_settings: ModelSettings,
    ) -> ModelResponse:
        response = await self._client.messages.create(
            **self._request_kwargs(
                messages=messages,
                model_settings=model_settings,
            )
        )
        return self._to_model_response(response)

    @asynccontextmanager
    async def stream_chat(
        self,
        *,
        messages: list[Message],
        model_settings: ModelSettings,
    ) -> AsyncIterator[AnthropicStreamedResponse]:
        stream_iter = await self._client.messages.create(
            **self._request_kwargs(
                messages=messages,
                model_settings=model_settings,
            ),
            stream=True,
        )
        response = AnthropicStreamedResponse(stream_iter)
        try:
            yield response
        finally:
            await response.close_stream()

    async def complete_structured(
        self,
        *,
        messages: list[Message],
        model_settings: ModelSettings,
        schema: type[T],
    ) -> T:
        """使用 Anthropic 原生 JSON Schema 约束结构化输出。"""
        response = await self._client.messages.create(
            **self._request_kwargs(
                messages=messages,
                model_settings=model_settings,
                output_format={
                    "type": "json_schema",
                    "schema": schema.model_json_schema(),
                },
            ),
        )
        content = "".join(
            block.text for block in response.content if block.type == "text"
        )
        if not content:
            raise ValueError("Anthropic response does not contain structured output.")
        return schema.model_validate_json(content)
