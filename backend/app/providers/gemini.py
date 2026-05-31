from typing import AsyncIterator, TypeVar
from contextlib import asynccontextmanager

import google.genai as genai
from google.genai import types
from google.genai.types import (
    GenerateContentResponse,
    ContentUnionDict,
    GenerateContentConfigDict,
)
from pydantic import BaseModel

from .base import StreamedResponse, Message
from app.core.config import settings


T = TypeVar("T", bound=BaseModel)


class GeminiStreamedResponse(StreamedResponse):
    def __init__(self, stream_iter: AsyncIterator[GenerateContentResponse]):
        self.stream_iter = stream_iter

    async def _get_stream_iter(self) -> AsyncIterator[str]:
        async for chunk in self.stream_iter:
            # TODO: 这里先简单实现，直接返回文本内容，
            # 未来扩展更多的中间操作，例如过滤、清洗、统计 token 使用量等
            if chunk.text:
                yield chunk.text


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

    def _map_messages_and_config(
        self,
        messages: list[Message],
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

        config = GenerateContentConfigDict(system_instruction=system_prompt)
        return [*history_contents, user_content], config

    def _map_json_schema(
        self, config: GenerateContentConfigDict, schema: type[T]
    ) -> GenerateContentConfigDict:
        """将 Pydantic 模型的 JSON Schema 转换为 Gemini LLM 请求接口需要的配置格式"""
        config["response_schema"] = schema.model_json_schema()
        config["response_mime_type"] = "application/json"
        return config

    @asynccontextmanager
    async def stream_chat(
        self, messages: list[Message]
    ) -> AsyncIterator[GeminiStreamedResponse]:
        """
        Gemini LLM 流式对话接口: 通过对 google.genai 的封装，提供简洁的流式对话接口,
        返回一个 GeminiStreamedResponse 对象，供业务层异步迭代获取流式响应内容
        """

        contents, config = self._map_messages_and_config(messages)

        stream_iter = await self._client.aio.models.generate_content_stream(
            model=self._model,
            config=config,
            contents=contents,
        )

        yield GeminiStreamedResponse(stream_iter=stream_iter)

    async def complete_structured(self, messages: list[Message], schema: type[T]) -> T:
        """
        Gemini LLM 结构化输出接口：按照指定的 Pydantic 模型 schema 对 LLM 输出进行解析和校验，
        返回一个符合 schema 定义的 Pydantic 模型实例
        """
        contents, config = self._map_messages_and_config(messages)
        config = self._map_json_schema(config, schema)

        response = await self._client.aio.models.generate_content(
            model=self._model,
            config=config,
            contents=contents,
        )

        if not response.text:
            raise ValueError("LLM response does not contain text content.")

        return schema.model_validate_json(response.text)
