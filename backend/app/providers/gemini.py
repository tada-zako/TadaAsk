from typing import AsyncIterator
from contextlib import asynccontextmanager

import google.genai as genai
from google.genai import types
from google.genai.types import GenerateContentResponse

from .base import ModelRequestContext, StreamedResponse
from app.providers.prompts import DEFAULT_SYSTEM_PROMPT
from app.rag import VectorQueryItem
from app.db.schemas import ChatMessageInternal
from app.core.config import settings


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
    def __init__(self, model_perf: str | None = None):
        if not settings.gemini_api_key:
            raise ValueError("Gemini API key is not set in the configuration.")

        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model = (
            model_perf or settings.gemini_model_perf or "gemini-2.5-flash"
        ).lower()

        # 模型工具配置
        # self.grounding_tool = types.Tool(google_search=types.GoogleSearch())
        # NOTE: 目前不通过 SDK 提供 google search 工具

    @property
    def model_name(self) -> str:
        """返回模型名称，供业务层记录日志等使用"""
        return self.model

    def construct_messages(
        self,
        document: list[VectorQueryItem],
        user_message: str,
        chat_history: list[ChatMessageInternal] | None = None,
    ) -> ModelRequestContext[types.ContentOrDict]:
        """
        构建符合 Gemini LLM 请求接口格式的消息实例
        """
        history_contents: list[types.ContentOrDict] | None = None
        if chat_history:
            history_contents = [
                types.Content(
                    role="model" if entry.role == "assistant" else "user",
                    parts=[types.Part(text=entry.message)],
                )
                for entry in chat_history
            ]

        # NOTE: 目前只提供静态系统提示词
        system_prompt = DEFAULT_SYSTEM_PROMPT

        if document:
            # 允许 document 为空
            context = "\n<Context>\n"
            for doc in document:
                context += (
                    f"[context{doc.id}]:\n{doc.document}\n"
                    + f"Metadata: {doc.metadata}\n\n"
                )
            context += "</Context>\n"

            user_message = (
                context + "\n<user_message>\n" + user_message + "\n</user_message>\n"
            )

        return ModelRequestContext(
            system_prompt=system_prompt,
            user_message=user_message,
            chat_history=history_contents,
        )

    @asynccontextmanager
    async def stream_chat(
        self, context: ModelRequestContext[types.ContentOrDict]
    ) -> AsyncIterator[GeminiStreamedResponse]:
        """
        Gemini LLM 流式对话接口: 通过对 google.genai 的封装，提供简洁的流式对话接口,
        返回一个 GeminiStreamedResponse 对象，供业务层异步迭代获取流式响应内容
        """

        stream_iter = await self.client.aio.models.generate_content_stream(
            model=self.model,
            config=types.GenerateContentConfig(
                system_instruction=context.system_prompt,
            ),
            contents=[
                context.chat_history,
                types.Content(
                    role="user", parts=[types.Part(text=context.user_message)]
                ),
            ],
        )
        yield GeminiStreamedResponse(stream_iter=stream_iter)
