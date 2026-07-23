"""OpenAI-compatible Provider 的请求生命周期编排。"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Literal, TypeVar, overload

from openai import AsyncOpenAI, AsyncStream
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionChunk,
    ChatCompletionMessageParam,
)
from pydantic import BaseModel

from ...base import Message, ModelResponse, ModelSettings, StreamedResponse


T = TypeVar("T", bound=BaseModel)


class OpenAICompatibleModel(ABC):
    """只编排 Chat Completions 调用，协议细节由具体 adapter 实现。"""

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

    @abstractmethod
    def _map_messages(
        self,
        messages: list[Message],
    ) -> list[ChatCompletionMessageParam]:
        """转换消息格式。"""
        raise NotImplementedError

    @abstractmethod
    def _build_completion_params(
        self,
        *,
        model_settings: ModelSettings,
        stream: bool,
        schema: type[BaseModel] | None,
    ) -> dict[str, Any]:
        """构造当前 Provider/Model 的完整生成参数。"""
        raise NotImplementedError

    @abstractmethod
    def _to_model_response(self, response: ChatCompletion) -> ModelResponse:
        """转换非流式响应。"""
        raise NotImplementedError

    @abstractmethod
    def _to_streamed_response(
        self,
        stream: AsyncStream[ChatCompletionChunk],
    ) -> StreamedResponse:
        """封装流式响应。"""
        raise NotImplementedError

    @abstractmethod
    def _to_structured_result(
        self,
        response: ChatCompletion,
        schema: type[T],
    ) -> T:
        """解析并校验结构化响应。"""
        raise NotImplementedError

    @overload
    async def _create_completion(
        self,
        *,
        messages: list[Message],
        model_settings: ModelSettings,
        stream: Literal[False] = False,
        schema: type[BaseModel] | None = None,
    ) -> ChatCompletion: ...

    @overload
    async def _create_completion(
        self,
        *,
        messages: list[Message],
        model_settings: ModelSettings,
        stream: Literal[True],
        schema: type[BaseModel] | None = None,
    ) -> AsyncStream[ChatCompletionChunk]: ...

    async def _create_completion(
        self,
        *,
        messages: list[Message],
        model_settings: ModelSettings,
        stream: bool = False,
        schema: type[BaseModel] | None = None,
    ) -> ChatCompletion | AsyncStream[ChatCompletionChunk]:
        request: dict[str, Any] = {
            "model": self._model,
            "messages": self._map_messages(messages),
            "timeout": model_settings.timeout,
            "stream": stream,
        }
        request.update(
            self._build_completion_params(
                model_settings=model_settings,
                stream=stream,
                schema=schema,
            )
        )
        return await self._client.chat.completions.create(**request)

    async def chat(
        self,
        *,
        messages: list[Message],
        model_settings: ModelSettings,
    ) -> ModelResponse:
        response = await self._create_completion(
            messages=messages,
            model_settings=model_settings,
        )
        return self._to_model_response(response)

    @asynccontextmanager
    async def stream_chat(
        self,
        *,
        messages: list[Message],
        model_settings: ModelSettings,
    ) -> AsyncIterator[StreamedResponse]:
        stream = await self._create_completion(
            messages=messages,
            model_settings=model_settings,
            stream=True,
        )
        response = self._to_streamed_response(stream)
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
        response = await self._create_completion(
            messages=messages,
            model_settings=model_settings,
            schema=schema,
        )
        return self._to_structured_result(response, schema)
