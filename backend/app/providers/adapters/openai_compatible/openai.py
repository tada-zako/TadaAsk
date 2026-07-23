"""OpenAI 官方 Provider。"""

from typing import Any

from openai.types import chat
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel

from ...base import ModelSettings
from .standard import StandardOpenAICompatibleModel


class OpenAIModel(StandardOpenAICompatibleModel):
    def __init__(self, *, model_perf: str, api_key: str, base_url: str | None = None):
        super().__init__(
            model_perf=model_perf,
            provider_name="openai",
            api_key=api_key,
            base_url=base_url,
        )

    def _map_system_message(self, content: str) -> ChatCompletionMessageParam:
        return chat.ChatCompletionDeveloperMessageParam(
            role="developer",
            content=content,
        )

    def _build_completion_params(
        self,
        *,
        model_settings: ModelSettings,
        stream: bool,
        schema: type[BaseModel] | None,
    ) -> dict[str, Any]:
        params = super()._build_completion_params(
            model_settings=model_settings,
            stream=stream,
            schema=schema,
        )
        params.update(self._thinking_params(model_settings))
        if stream:
            params.update(self._stream_params())
        return params

    def _thinking_params(self, model_settings: ModelSettings) -> dict[str, Any]:
        level = "medium" if model_settings.thinking is True else model_settings.thinking
        return {"reasoning_effort": level} if level is not False else {}

    def _stream_params(self) -> dict[str, Any]:
        return {"stream_options": {"include_usage": True}}
