from typing import AsyncIterator, Literal, TypeVar, overload
from dataclasses import dataclass
from contextlib import asynccontextmanager

from openai import AsyncOpenAI, AsyncStream, Omit, omit
from openai.types import chat, shared_params, ReasoningEffort
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionChunk,
    ChatCompletionMessageParam,
)
from openai.types.completion_usage import CompletionUsage
from pydantic import BaseModel

from .base import (
    StreamedResponse,
    Message,
    ModelSettings,
    ModelResponse,
    TokenUsage,
    ThinkingLevel,
)
from app.core.constants import ChatMessageRole


DEFAULT_RESPONSE_FORMAT_NAME = "response_format"
BUILT_IN_OPENAI_COMPATIBLE_PROVIDERS = {"openai", "deepseek", "ollama"}


T = TypeVar("T", bound=BaseModel)


@dataclass
class OpenAIEndpoint:
    """OpenAI 兼容接口配置"""

    endpoint_name: str
    api_key: str
    base_url: str | None = None

    @classmethod
    def deepseek(cls, api_key: str, base_url: str | None = None) -> "OpenAIEndpoint":
        """DeepSeek 兼容接口配置"""
        return cls(
            api_key=api_key,
            base_url=base_url or "https://api.deepseek.com",
            endpoint_name="deepseek",
        )

    @classmethod
    def openai(cls, api_key: str, base_url: str | None = None) -> "OpenAIEndpoint":
        """OpenAI 官方接口配置"""
        return cls(
            api_key=api_key,
            base_url=base_url,  # OpenAI 官方 API 使用默认 base URL，无需配置
            endpoint_name="openai",
        )

    @classmethod
    def ollama(
        cls, api_key: str | None = None, base_url: str | None = None
    ) -> "OpenAIEndpoint":
        """Ollama 兼容接口配置，默认指向本地 Ollama 服务"""
        return cls(
            api_key="ollama",  # Ollama 本地服务通常不需要 API Key
            base_url=base_url or "http://localhost:11434",
            endpoint_name="ollama",
        )

    @classmethod
    def custom(
        cls,
        *,
        endpoint_name: str,
        api_key: str,
        base_url: str,
    ) -> "OpenAIEndpoint":
        """用户自定义 OpenAI 兼容接口配置。"""
        if not endpoint_name:
            raise ValueError("Custom endpoint name is required.")
        if not base_url:
            raise ValueError(
                "Base URL is required for custom OpenAI-compatible providers."
            )
        return cls(
            api_key=api_key,
            base_url=base_url,
            endpoint_name=endpoint_name,
        )


class OpenAIStreamedResponse(StreamedResponse):
    def __init__(self, stream_iter: AsyncStream[ChatCompletionChunk]):
        super().__init__()
        self.stream_iter = stream_iter

    def _update_usage(self, raw_usage: CompletionUsage) -> None:
        """更新 OpenAI 兼容接口返回的 token 用量统计。"""
        self._usage.input_tokens = raw_usage.prompt_tokens or 0
        self._usage.output_tokens = raw_usage.completion_tokens or 0
        self._usage.raw_usage = raw_usage

    async def _get_stream_iter(self) -> AsyncIterator[str]:
        async for chunk in self.stream_iter:
            if chunk.usage:
                # 更新 token 用量统计
                self._update_usage(chunk.usage)

            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            if choice.delta is None:
                continue

            # 只处理文本内容情况
            content = choice.delta.content
            if content:
                # 追加到缓存区
                self._text_buffer.append(content)
                yield content

    async def close_stream(self) -> None:
        await self.stream_iter.close()


class OpenAIChatModel:
    def __init__(self, model_perf: str, endpoint: OpenAIEndpoint):
        if not endpoint.api_key:
            raise ValueError(
                f"API key is not set for endpoint {endpoint.endpoint_name}."
            )

        self._model = model_perf
        self._base_url = endpoint.base_url
        self._provider_name = endpoint.endpoint_name
        self._client = AsyncOpenAI(base_url=endpoint.base_url, api_key=endpoint.api_key)

    @property
    def model_name(self) -> str:
        """返回模型名称，供业务层记录日志等使用"""
        return self._model

    @property
    def provider_name(self) -> str:
        """返回模型所属的 provider 名称，供业务层记录日志等使用"""
        return self._provider_name

    @property
    def is_custom_provider(self) -> bool:
        """是否为用户自定义 OpenAI-compatible provider。"""
        return self.provider_name not in BUILT_IN_OPENAI_COMPATIBLE_PROVIDERS

    def _translate_thinking(self, thinking: ThinkingLevel) -> ReasoningEffort | Omit:
        """通用的 thinking 配置转换为 Openai Compatible LLM 内部 thinking_config 格式"""
        if self.is_custom_provider:
            # 自定义 provider 仅假设为广义 OpenAI-compatible，不默认支持 reasoning_effort。
            return omit

        level_map = {
            True: "medium",
            False: None,
            "minimal": "minimal",
            "low": "low",
            "medium": "medium",
            "high": "high",
            "xhigh": "xhigh",
        }

        thinking_value = level_map.get(thinking, "medium")  # 默认使用 "medium" 思考强度

        if thinking_value is None:
            return omit
        return thinking_value

    def _map_messages(
        self, messages: list[Message]
    ) -> list[ChatCompletionMessageParam]:
        """将通用 Message 转换为 OpenAI SDK 兼容的 ChatCompletionMessageParam 列表"""
        openai_messages: list[ChatCompletionMessageParam] = []
        for msg in messages:
            if msg.role == ChatMessageRole.SYSTEM:
                if self.provider_name == "openai":
                    # 只有 openai 支持 developer role
                    openai_messages.append(
                        chat.ChatCompletionDeveloperMessageParam(
                            role="developer", content=msg.content
                        )
                    )
                else:
                    # 其他模型一致使用 system role
                    openai_messages.append(
                        chat.ChatCompletionSystemMessageParam(
                            role="system", content=msg.content
                        )
                    )
            elif msg.role == ChatMessageRole.USER:
                openai_messages.append(
                    chat.ChatCompletionUserMessageParam(
                        role="user", content=msg.content
                    )
                )
            elif msg.role == ChatMessageRole.ASSISTANT:
                openai_messages.append(
                    chat.ChatCompletionAssistantMessageParam(
                        role="assistant", content=msg.content
                    )
                )
            else:
                raise ValueError(f"Unsupported message role: {msg.role}")

        return openai_messages

    @overload
    async def _completions_create(
        self,
        *,
        messages: list[Message],
        model_settings: ModelSettings,
        stream: Literal[False] = False,
        response_format: chat.completion_create_params.ResponseFormat | None = None,
    ) -> ChatCompletion:
        """非流式返回类型"""
        ...

    @overload
    async def _completions_create(
        self,
        *,
        messages: list[Message],
        model_settings: ModelSettings,
        stream: Literal[True],
        response_format: chat.completion_create_params.ResponseFormat | None = None,
    ) -> AsyncStream[ChatCompletionChunk]:
        """流式返回类型"""
        ...

    async def _completions_create(
        self,
        *,
        messages: list[Message],
        model_settings: ModelSettings,
        stream: bool = False,
        response_format: chat.completion_create_params.ResponseFormat | None = None,
    ) -> ChatCompletion | AsyncStream[ChatCompletionChunk]:
        """统一创建 OpenAI-compatible chat completion 响应。"""
        openai_messages = self._map_messages(messages)

        return await self._client.chat.completions.create(
            model=self._model,
            messages=openai_messages,
            response_format=response_format if response_format is not None else omit,
            temperature=model_settings.temperature,
            top_p=model_settings.top_p,
            max_completion_tokens=model_settings.max_tokens,
            timeout=model_settings.timeout,
            reasoning_effort=self._translate_thinking(model_settings.thinking),
            stream=stream,
            stream_options={"include_usage": True} if stream else omit,
        )

    def _map_json_schema(
        self, schema: type[T]
    ) -> chat.completion_create_params.ResponseFormat:
        """将 Pydantic 模型的 JSON Schema 转换为 OpenAI SDK 兼容的 JSON Schema 格式"""
        response_format: shared_params.ResponseFormatJSONSchema = {
            "type": "json_schema",
            "json_schema": {
                "name": DEFAULT_RESPONSE_FORMAT_NAME,
                "schema": schema.model_json_schema(),
            },
        }
        return response_format

    def _process_response(self, response: ChatCompletion) -> ModelResponse:
        content = response.choices[0].message.content or ""
        raw_usage = response.usage
        return ModelResponse(
            text=content,
            usage=TokenUsage(
                input_tokens=raw_usage.prompt_tokens or 0,
                output_tokens=raw_usage.completion_tokens or 0,
                raw_usage=raw_usage,
            )
            if raw_usage
            else TokenUsage(),
        )

    async def chat(
        self,
        *,
        messages: list[Message],
        model_settings: ModelSettings,
    ) -> ModelResponse:
        """
        OpenAI 兼容接口的非流式文本生成。
        """
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
        """
        OpenAI LLM 流式聊天接口：返回一个异步迭代器，逐步产出 LLM 的响应内容
        """

        stream_iter = await self._completions_create(
            messages=messages,
            model_settings=model_settings,
            stream=True,
        )

        yield OpenAIStreamedResponse(stream_iter=stream_iter)

    async def complete_structured(
        self,
        *,
        messages: list[Message],
        model_settings: ModelSettings,
        schema: type[T],
    ) -> T:
        """
        OpenAI 兼容接口结构化输出：按照指定的 Pydantic 模型 schema 对 LLM 输出进行解析和校验，
        返回一个符合 schema 定义的 Pydantic 模型实例
        """
        response_format = self._map_json_schema(schema)

        response = await self._completions_create(
            messages=messages,
            response_format=response_format,
            model_settings=model_settings,
        )

        content = response.choices[0].message.content
        if not content:
            raise ValueError("LLM response does not contain content.")

        return schema.model_validate_json(content)
