from typing import AsyncIterator, TypeVar
from dataclasses import dataclass
from contextlib import asynccontextmanager

from openai import AsyncOpenAI, AsyncStream
from openai.types.chat.chat_completion_chunk import ChatCompletionChunk
from pydantic import BaseModel

from .base import StreamedResponse, Message, ModelRequestParameters
from .openai_compatible import OpenAIEndpoint
from app.core.config import settings


T = TypeVar("T", bound=BaseModel)


@dataclass
class OpenAIEndpoint:
    """OpenAI 兼容接口配置"""

    endpoint_name: str
    api_key: str | None = None
    base_url: str | None = None

    @classmethod
    def deepseek(cls) -> OpenAIEndpoint:
        """DeepSeek 兼容接口配置"""
        return cls(
            api_key=settings.deepseek_api_key,
            base_url="https://api.deepseek.com",
            endpoint_name="deepseek",
        )

    @classmethod
    def openai(cls) -> OpenAIEndpoint:
        """OpenAI 官方接口配置"""
        return cls(
            api_key=settings.gemini_api_key,
            base_url=None,  # OpenAI 官方 API 使用默认 base URL，无需配置
            endpoint_name="openai",
        )

    @classmethod
    def ollama(cls) -> OpenAIEndpoint:
        """Ollama 兼容接口配置，默认指向本地 Ollama 服务"""
        return cls(
            api_key=None,  # Ollama 本地服务通常不需要 API Key
            base_url="http://localhost:11434",
            endpoint_name="ollama",
        )


class OpenAIStreamedResponse(StreamedResponse):
    def __init__(self, stream_iter: AsyncStream[ChatCompletionChunk]):
        self.stream_iter = stream_iter

    async def _get_stream_iter(self) -> AsyncIterator[str]:
        async for chunk in self.stream_iter:
            # TODO: 这里先简单实现，直接返回文本内容，
            # 未来扩展更多的中间操作，例如过滤、清洗、统计 token 使用量等
            if chunk.text:
                yield chunk.text


class OpenAIChatModel:
    def __init__(self, model_perf: str, endpoint: OpenAIEndpoint):
        if not endpoint.api_key:
            raise ValueError(
                f"API key is not set for endpoint {endpoint.endpoint_name}."
            )

        self._model = model_perf
        self._client = AsyncOpenAI(base_url=endpoint.base_url, api_key=endpoint.api_key)

    @property
    def model_name(self) -> str:
        """返回模型名称，供业务层记录日志等使用"""
        return self._model

    def _build_content_and_config(
        self, messages: list[Message], request_parameters: ModelRequestParameters
    ) -> tuple[list[ContentUnionDict], GenerateContentConfigDict]:
        """将通用 Message 转换为 Gemini LLM 请求接口需要的内容格式和配置格式"""
        system_prompt = next(
            (msg.content for msg in reversed(messages) if msg.role == "system"), ""
        )

        last_user_msg = messages[-1]
        if last_user_msg.role != "user":
            raise ValueError("The last message must be a user message.")
        user_content = types.Content(
            role="user", parts=[types.Part(text=last_user_msg.content)]
        )

        # 历史对话构建，过滤掉 system 消息和 user_message
        history_contents: list[types.ContentOrDict] = []
        for msg in messages[:-1]:
            if msg.role == "system":
                continue
            role = "model" if msg.role == "assistant" else "user"
            history_contents.append(
                types.Content(role=role, parts=[types.Part(text=msg.content)])
            )

        # 处理结构化输出相关的配置
        response_schema = None
        response_mime_type = None
        if request_parameters.output_mode == "structured":
            if request_parameters.output_schema is None:
                raise ValueError(
                    "output_schema must be provided when output_mode is 'structured'."
                )
            # 这里简单实现为将 Pydantic 模型的 JSON Schema 作为系统提示词的一部分，
            # 未来可以设计更复杂的提示词模板来引导 LLM 输出符合 schema 定义的内容
            response_schema = request_parameters.output_schema.model_json_schema()
            response_mime_type = "application/json"

        config = GenerateContentConfigDict(
            system_instruction=system_prompt,
            response_mime_type=response_mime_type,
            response_schema=response_schema,
        )

        return [*history_contents, user_content], config

    @asynccontextmanager
    async def stream_chat(
        self, messages: list[Message]
    ) -> AsyncIterator[OpenAIStreamedResponse]:
        """
        Gemini LLM 流式对话接口: 通过对 google.genai 的封装，提供简洁的流式对话接口,
        返回一个 GeminiStreamedResponse 对象，供业务层异步迭代获取流式响应内容
        """

        contents, config = self._build_content_and_config(
            messages, ModelRequestParameters()
        )

        stream_iter = await self._client.chat.completions.create(
            model=self.model,
            config=config,
            contents=contents,
        )

        yield GeminiStreamedResponse(stream_iter=stream_iter)

    async def complete_structured(self, messages: list[Message], schema: type[T]) -> T:
        """
        Gemini LLM 结构化输出接口：按照指定的 Pydantic 模型 schema 对 LLM 输出进行解析和校验，
        返回一个符合 schema 定义的 Pydantic 模型实例
        """
        contents, config = self._build_content_and_config(
            messages,
            ModelRequestParameters(output_mode="structured", output_schema=schema),
        )

        response = await self.client.aio.models.generate_content(
            model=self.model,
            config=config,
            contents=contents,
        )

        if not response.text:
            raise ValueError("LLM response does not contain text content.")

        return schema.model_validate_json(response.text)
