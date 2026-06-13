from typing import AsyncIterator, TypeVar, cast, Any
from contextlib import asynccontextmanager

import google.genai as genai
from google.genai import types
from google.genai.types import (
    GenerateContentResponse,
    ContentUnionDict,
    GenerateContentConfigDict,
    HttpOptionsDict,
    ThinkingConfigDict,
    GenerateContentResponseUsageMetadata,
)
from pydantic import BaseModel

from .base import (
    StreamedResponse,
    Message,
    TokenUsage,
    ModelSettings,
    ModelResponse,
    ThinkingLevel,
)
from app.core.config import settings
from app.core.constants import ChatMessageRole


T = TypeVar("T", bound=BaseModel)


class GeminiStreamedResponse(StreamedResponse):
    def __init__(self, response: AsyncIterator[GenerateContentResponse]):
        super().__init__()
        self._response = response

    def _update_usage(self, metadata: GenerateContentResponseUsageMetadata) -> None:
        """更新 token 用量统计"""
        self._usage.input_tokens = metadata.prompt_token_count or 0
        self._usage.cache_read_tokens = metadata.cached_content_token_count or 0
        self._usage.reasoning_tokens = metadata.thoughts_token_count or 0
        self._usage.output_tokens = metadata.candidates_token_count or 0
        self._usage.raw_usage = metadata

    async def _get_stream_iter(self) -> AsyncIterator[str]:
        async for chunk in self._response:
            # 更新 token 用量统计
            if chunk.usage_metadata:
                self._update_usage(chunk.usage_metadata)

            if chunk.text:
                # 保存生成文本到缓冲区
                self._text_buffer.append(chunk.text)

                yield chunk.text

    async def close_stream(self) -> None:
        if hasattr(self._response, "aclose"):
            try:
                await self._response.aclose()  # type: ignore
                return
            except RuntimeError as exc:
                if "asynchronous generator is already running" not in str(exc):
                    # 如果是因为生成器正在运行而无法关闭，则忽略该错误；否则，重新抛出异常
                    raise

        # 避免底层 SDK 不支持显式关闭流式连接时
        raise NotImplementedError(
            "The underlying stream does not support explicit closure."
        )


class GeminiModel:
    def __init__(self, model_perf: str):
        if not settings.gemini_api_key:
            raise ValueError("Gemini API key is not set in the configuration.")

        self._model = model_perf
        self._client = genai.Client(api_key=settings.gemini_api_key)

        # 模型工具配置
        # self.grounding_tool = types.Tool(google_search=types.GoogleSearch())
        # NOTE: 目前不通过 SDK 提供 google search 工具

    @property
    def model_name(self) -> str:
        """返回模型名称，供业务层记录日志等使用"""
        return self._model

    def _translate_thinking(self, thinking: ThinkingLevel) -> ThinkingConfigDict | None:
        if thinking is False:
            return ThinkingConfigDict(thinking_budget=0)

        # TODO: 需要基于不同模型实际的可选配置进行验证；
        # 这里先不做后端验证，相信一手前端...

        if thinking is True:
            return ThinkingConfigDict(
                include_thoughts=True, thinking_level=cast(Any, "MEDIUM")
            )

        level_map: dict[ThinkingLevel, str] = {
            "minimal": "MINIMAL",
            "low": "LOW",
            "medium": "MEDIUM",
            "high": "HIGH",
            "xhigh": "HIGH",  # 没有更高的等级
        }

        return ThinkingConfigDict(
            include_thoughts=True,
            thinking_level=cast(
                Any, level_map.get(thinking, "MEDIUM")
            ),  # 默认为 MEDIUM
        )

    def _map_messages(
        self,
        messages: list[Message],
    ) -> list[ContentUnionDict]:
        """将通用 Message 列表转换为 Gemini LLM 请求接口需要的内容列表和配置字典"""
        last_user_msg = messages[-1]
        if last_user_msg.role != ChatMessageRole.USER:
            raise ValueError("The last message must be a user message.")
        user_content = types.Content(
            role="user", parts=[types.Part(text=last_user_msg.content)]
        )

        # 历史对话构建，system 消息统一由 _map_system_instruction 处理
        history_contents: list[types.ContentOrDict] = []
        for msg in messages[:-1]:
            if msg.role == ChatMessageRole.SYSTEM:
                continue
            role = "model" if msg.role == ChatMessageRole.ASSISTANT else "user"

            history_contents.append(
                types.Content(role=role, parts=[types.Part(text=msg.content)])
            )

        return [*history_contents, user_content]

    def _map_system_instruction(self, messages: list[Message]) -> str:
        """将明确的 system 消息映射为 Gemini system_instruction。"""
        return "\n\n".join(
            msg.content for msg in messages if msg.role == ChatMessageRole.SYSTEM
        )

    def _map_config(
        self,
        *,
        model_settings: ModelSettings,
        messages: list[Message],
        schema: type[T] | None = None,
    ) -> GenerateContentConfigDict:
        """将通用 ModelSettings 转换为 Gemini LLM 请求接口需要的配置格式"""
        system_instruction = self._map_system_instruction(messages)

        # 构建 Gemini 请求配置
        response_mime_type = None
        response_schema = None

        if schema:
            response_mime_type = "application/json"
            response_schema = schema.model_json_schema()

        http_options: HttpOptionsDict | None = None
        if timeout := model_settings.timeout:
            http_options = {"timeout": int(timeout * 1000)}  # 转换为毫秒

        config = GenerateContentConfigDict(
            http_options=http_options,
            system_instruction=system_instruction,
            temperature=model_settings.temperature,
            top_p=model_settings.top_p,
            max_output_tokens=model_settings.max_tokens,
            thinking_config=self._translate_thinking(model_settings.thinking),
            response_mime_type=response_mime_type,
            response_schema=response_schema,
        )

        return config

    def _process_response(self, response: GenerateContentResponse) -> ModelResponse:
        """
        将 Gemini LLM 的响应转换为通用 ModelResponse 格式；
        主要是统计 token 用量
        """
        usage = response.usage_metadata
        return ModelResponse(
            text=response.text or "",
            usage=TokenUsage(
                input_tokens=usage.prompt_token_count or 0,
                cache_read_tokens=usage.cached_content_token_count or 0,
                reasoning_tokens=usage.thoughts_token_count or 0,
                output_tokens=usage.candidates_token_count or 0,
                raw_usage=usage,
            )
            if usage
            else TokenUsage(),
        )

    async def chat(
        self,
        *,
        messages: list[Message],
        model_settings: ModelSettings,
    ) -> ModelResponse:
        """
        Gemini LLM 文本生成接口: 通过对 google.genai 的封装，提供简洁的文本生成接口,
        返回一个 ModelResponse 对象，包含生成文本内容和 token 用量等信息
        """
        contents = self._map_messages(messages)
        config = self._map_config(model_settings=model_settings, messages=messages)

        response = await self._client.aio.models.generate_content(
            model=self._model,
            config=config,
            contents=contents,
        )

        return self._process_response(response)

    @asynccontextmanager
    async def stream_chat(
        self,
        *,
        messages: list[Message],
        model_settings: ModelSettings,
    ) -> AsyncIterator[GeminiStreamedResponse]:
        """
        Gemini LLM 流式对话接口: 通过对 google.genai 的封装，提供简洁的流式对话接口,
        返回一个 GeminiStreamedResponse 对象，供业务层异步迭代获取流式响应内容
        """

        contents = self._map_messages(messages)
        config = self._map_config(model_settings=model_settings, messages=messages)

        response = await self._client.aio.models.generate_content_stream(
            model=self._model,
            config=config,
            contents=contents,
        )

        yield GeminiStreamedResponse(response=response)

    async def complete_structured(
        self,
        *,
        messages: list[Message],
        model_settings: ModelSettings,
        schema: type[T],
    ) -> T:
        """
        Gemini LLM 结构化输出接口：按照指定的 Pydantic 模型 schema 对 LLM 输出进行解析和校验，
        返回一个符合 schema 定义的 Pydantic 模型实例
        """
        contents = self._map_messages(messages)
        config = self._map_config(
            messages=messages,
            model_settings=model_settings,
            schema=schema,
        )

        response = await self._client.aio.models.generate_content(
            model=self._model,
            config=config,
            contents=contents,
        )

        if not response.text:
            raise ValueError("LLM response does not contain text content.")

        return schema.model_validate_json(response.text)
