"""OpenAI-compatible Provider 的共享传输实现。"""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any, Literal, TypeVar, overload

from openai import AsyncOpenAI, AsyncStream, omit
from openai.types import chat, shared_params
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionChunk,
    ChatCompletionMessageParam,
)
from pydantic import BaseModel

from app.core.constants import ChatMessageRole

from ...base import Message, ModelResponse, ModelSettings, StreamedResponse, TokenUsage


DEFAULT_RESPONSE_FORMAT_NAME = "response_format"
T = TypeVar("T", bound=BaseModel)
StreamUsageReader = Callable[[ChatCompletionChunk, TokenUsage], None]
StreamContentReader = Callable[[ChatCompletionChunk], str | None]


def _usage_field(value: Any, name: str, default: Any = 0) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _update_token_usage(usage: TokenUsage, raw_usage: Any) -> None:
    """兼容 SDK 对象与厂商扩展字典，并避免重复计算 reasoning token。"""
    completion_tokens = _usage_field(raw_usage, "completion_tokens", 0) or 0
    details = _usage_field(raw_usage, "completion_tokens_details", None)
    reasoning_tokens = _usage_field(details, "reasoning_tokens", 0) or 0
    usage.input_tokens = _usage_field(raw_usage, "prompt_tokens", 0) or 0
    usage.reasoning_tokens = reasoning_tokens
    usage.output_tokens = max(completion_tokens - reasoning_tokens, 0)
    usage.raw_usage = raw_usage


class OpenAIStreamedResponse(StreamedResponse):
    def __init__(
        self,
        stream_iter: AsyncStream[ChatCompletionChunk],
        usage_reader: StreamUsageReader,
        content_reader: StreamContentReader,
    ) -> None:
        super().__init__()
        self.stream_iter = stream_iter
        self._usage_reader = usage_reader
        self._content_reader = content_reader

    async def _get_stream_iter(self) -> AsyncIterator[str]:
        async for chunk in self.stream_iter:
            self._usage_reader(chunk, self._usage)

            content = self._content_reader(chunk)
            if content:
                self._text_buffer.append(content)
                yield content

    async def close_stream(self) -> None:
        await self.stream_iter.close()


class OpenAICompatibleModel:
    """复用 OpenAI SDK 的基础实现；Provider 差异由子类私有方法处理。"""

    def __init__(
        self,
        *,
        model_perf: str,
        provider_name: str,
        api_key: str,
        base_url: str | None = None,
    ) -> None:
        if not api_key:
            raise ValueError(f"API key is not set for provider {provider_name}.")

        self._model = model_perf
        self._provider_name = provider_name
        self._client = AsyncOpenAI(base_url=base_url, api_key=api_key)

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def provider_name(self) -> str:
        return self._provider_name

    def _use_developer_role(self) -> bool:
        return False

    def _provider_request_kwargs(
        self,
        model_settings: ModelSettings,
        *,
        stream: bool,
    ) -> dict[str, Any]:
        """兼容接口默认不发送厂商扩展参数。"""
        return {}

    def _max_tokens_parameter(self) -> str:
        return "max_completion_tokens"

    def _update_stream_usage(
        self,
        chunk: ChatCompletionChunk,
        usage: TokenUsage,
    ) -> None:
        raw_usage = chunk.usage
        if raw_usage is None:
            return
        _update_token_usage(usage, raw_usage)

    def _read_stream_content(self, chunk: ChatCompletionChunk) -> str | None:
        if not chunk.choices or chunk.choices[0].delta is None:
            return None
        return chunk.choices[0].delta.content

    def _stream_content_reader(self) -> StreamContentReader:
        return self._read_stream_content

    def _map_messages(
        self,
        messages: list[Message],
    ) -> list[ChatCompletionMessageParam]:
        openai_messages: list[ChatCompletionMessageParam] = []
        for message in messages:
            if message.role == ChatMessageRole.SYSTEM:
                if self._use_developer_role():
                    openai_messages.append(
                        chat.ChatCompletionDeveloperMessageParam(
                            role="developer",
                            content=message.content,
                        )
                    )
                else:
                    openai_messages.append(
                        chat.ChatCompletionSystemMessageParam(
                            role="system",
                            content=message.content,
                        )
                    )
            elif message.role == ChatMessageRole.USER:
                openai_messages.append(
                    chat.ChatCompletionUserMessageParam(
                        role="user",
                        content=message.content,
                    )
                )
            elif message.role == ChatMessageRole.ASSISTANT:
                openai_messages.append(
                    chat.ChatCompletionAssistantMessageParam(
                        role="assistant",
                        content=message.content,
                    )
                )
            else:
                raise ValueError(f"Unsupported message role: {message.role}")
        return openai_messages

    @overload
    async def _completions_create(
        self,
        *,
        messages: list[Message],
        model_settings: ModelSettings,
        stream: Literal[False] = False,
        response_format: chat.completion_create_params.ResponseFormat | None = None,
    ) -> ChatCompletion: ...

    @overload
    async def _completions_create(
        self,
        *,
        messages: list[Message],
        model_settings: ModelSettings,
        stream: Literal[True],
        response_format: chat.completion_create_params.ResponseFormat | None = None,
    ) -> AsyncStream[ChatCompletionChunk]: ...

    async def _completions_create(
        self,
        *,
        messages: list[Message],
        model_settings: ModelSettings,
        stream: bool = False,
        response_format: chat.completion_create_params.ResponseFormat | None = None,
    ) -> ChatCompletion | AsyncStream[ChatCompletionChunk]:
        request_kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": self._map_messages(messages),
            "response_format": response_format if response_format is not None else omit,
            "temperature": model_settings.temperature,
            "top_p": model_settings.top_p,
            "timeout": model_settings.timeout,
            "stream": stream,
        }
        request_kwargs[self._max_tokens_parameter()] = model_settings.max_tokens
        request_kwargs.update(
            self._provider_request_kwargs(model_settings, stream=stream)
        )
        return await self._client.chat.completions.create(**request_kwargs)

    def _map_json_schema(
        self,
        schema: type[T],
    ) -> chat.completion_create_params.ResponseFormat:
        response_format: shared_params.ResponseFormatJSONSchema = {
            "type": "json_schema",
            "json_schema": {
                "name": DEFAULT_RESPONSE_FORMAT_NAME,
                "schema": schema.model_json_schema(),
            },
        }
        return response_format

    def _map_json_object(
        self,
        schema: type[T],
    ) -> chat.completion_create_params.ResponseFormat:
        del schema
        return {"type": "json_object"}

    def _process_response(self, response: ChatCompletion) -> ModelResponse:
        content = response.choices[0].message.content or ""
        raw_usage = response.usage
        usage = TokenUsage()
        if raw_usage:
            _update_token_usage(usage, raw_usage)
        return ModelResponse(text=content, usage=usage)

    async def chat(
        self,
        *,
        messages: list[Message],
        model_settings: ModelSettings,
    ) -> ModelResponse:
        response = await self._completions_create(
            messages=messages,
            model_settings=model_settings,
        )
        return self._process_response(response)

    @asynccontextmanager
    async def stream_chat(
        self,
        *,
        messages: list[Message],
        model_settings: ModelSettings,
    ) -> AsyncIterator[OpenAIStreamedResponse]:
        stream_iter = await self._completions_create(
            messages=messages,
            model_settings=model_settings,
            stream=True,
        )
        response = OpenAIStreamedResponse(
            stream_iter,
            self._update_stream_usage,
            self._stream_content_reader(),
        )
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
        response = await self._completions_create(
            messages=messages,
            response_format=self._map_json_schema(schema),
            model_settings=model_settings,
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("LLM response does not contain content.")
        return schema.model_validate_json(content)
