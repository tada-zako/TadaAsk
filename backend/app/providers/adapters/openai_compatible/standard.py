"""标准 OpenAI Chat Completions 请求与响应实现。"""

from collections.abc import AsyncIterator
from typing import Any, TypeVar

from openai import AsyncStream
from openai.types import chat, shared_params
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionChunk,
    ChatCompletionMessageParam,
)
from pydantic import BaseModel

from app.core.constants import ChatMessageRole

from ...base import Message, ModelResponse, ModelSettings, StreamedResponse, TokenUsage
from .base import OpenAICompatibleModel


DEFAULT_RESPONSE_FORMAT_NAME = "response_format"
T = TypeVar("T", bound=BaseModel)


def _usage_field(value: Any, name: str, default: Any = 0) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def update_token_usage(usage: TokenUsage, raw_usage: Any) -> None:
    """读取标准 OpenAI usage，并避免重复计算 reasoning token。"""
    completion_tokens = _usage_field(raw_usage, "completion_tokens", 0) or 0
    details = _usage_field(raw_usage, "completion_tokens_details", None)
    reasoning_tokens = _usage_field(details, "reasoning_tokens", 0) or 0
    usage.input_tokens = _usage_field(raw_usage, "prompt_tokens", 0) or 0
    usage.reasoning_tokens = reasoning_tokens
    usage.output_tokens = max(completion_tokens - reasoning_tokens, 0)
    usage.raw_usage = raw_usage


class StandardOpenAIStreamedResponse(StreamedResponse):
    """标准 OpenAI 增量文本和顶层 usage 响应。"""

    def __init__(self, stream: AsyncStream[ChatCompletionChunk]) -> None:
        super().__init__()
        self.stream = stream

    def _update_usage(self, chunk: ChatCompletionChunk) -> None:
        if chunk.usage is not None:
            update_token_usage(self._usage, chunk.usage)

    def _read_content(self, chunk: ChatCompletionChunk) -> str | None:
        if not chunk.choices or chunk.choices[0].delta is None:
            return None
        return chunk.choices[0].delta.content

    async def _get_stream_iter(self) -> AsyncIterator[str]:
        async for chunk in self.stream:
            self._update_usage(chunk)
            content = self._read_content(chunk)
            if content:
                self._text_buffer.append(content)
                yield content

    async def close_stream(self) -> None:
        await self.stream.close()


class StandardOpenAICompatibleModel(OpenAICompatibleModel):
    """标准 OpenAI-compatible 方言，也作为自定义 Provider 的安全默认值。"""

    def _map_system_message(self, content: str) -> ChatCompletionMessageParam:
        return chat.ChatCompletionSystemMessageParam(role="system", content=content)

    def _map_messages(
        self,
        messages: list[Message],
    ) -> list[ChatCompletionMessageParam]:
        mapped: list[ChatCompletionMessageParam] = []
        for message in messages:
            if message.role == ChatMessageRole.SYSTEM:
                mapped.append(self._map_system_message(message.content))
            elif message.role == ChatMessageRole.USER:
                mapped.append(
                    chat.ChatCompletionUserMessageParam(
                        role="user",
                        content=message.content,
                    )
                )
            elif message.role == ChatMessageRole.ASSISTANT:
                mapped.append(
                    chat.ChatCompletionAssistantMessageParam(
                        role="assistant",
                        content=message.content,
                    )
                )
            else:
                raise ValueError(f"Unsupported message role: {message.role}")
        return mapped

    def _json_schema_format(
        self,
        schema: type[BaseModel],
    ) -> chat.completion_create_params.ResponseFormat:
        response_format: shared_params.ResponseFormatJSONSchema = {
            "type": "json_schema",
            "json_schema": {
                "name": DEFAULT_RESPONSE_FORMAT_NAME,
                "schema": schema.model_json_schema(),
            },
        }
        return response_format

    def _json_object_format(
        self,
    ) -> chat.completion_create_params.ResponseFormat:
        return {"type": "json_object"}

    def _build_completion_params(
        self,
        *,
        model_settings: ModelSettings,
        stream: bool,
        schema: type[BaseModel] | None,
    ) -> dict[str, Any]:
        del stream
        params: dict[str, Any] = {
            "temperature": model_settings.temperature,
            "top_p": model_settings.top_p,
            "max_completion_tokens": model_settings.max_tokens,
        }
        if schema is not None:
            params["response_format"] = self._json_schema_format(schema)
        return params

    def _to_model_response(self, response: ChatCompletion) -> ModelResponse:
        usage = TokenUsage()
        if response.usage is not None:
            update_token_usage(usage, response.usage)
        return ModelResponse(
            text=response.choices[0].message.content or "",
            usage=usage,
        )

    def _to_streamed_response(
        self,
        stream: AsyncStream[ChatCompletionChunk],
    ) -> StreamedResponse:
        return StandardOpenAIStreamedResponse(stream)

    def _to_structured_result(
        self,
        response: ChatCompletion,
        schema: type[T],
    ) -> T:
        content = response.choices[0].message.content
        if not content:
            raise ValueError("LLM response does not contain content.")
        return schema.model_validate_json(content)
