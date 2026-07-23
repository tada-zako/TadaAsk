"""Kimi 官方 Provider。"""

from typing import Any

from openai import AsyncStream
from openai.types.chat import ChatCompletionChunk
from pydantic import BaseModel

from ...base import ModelSettings
from .standard import (
    StandardOpenAICompatibleModel,
    StandardOpenAIStreamedResponse,
    update_token_usage,
)


class KimiStreamedResponse(StandardOpenAIStreamedResponse):
    """兼容 Kimi 在 choice 结束块中返回 usage 的行为。"""

    def _update_usage(self, chunk: ChatCompletionChunk) -> None:
        if chunk.usage is not None:
            update_token_usage(self._usage, chunk.usage)
            return
        for choice in chunk.choices:
            raw_usage = getattr(choice, "usage", None)
            if raw_usage is not None:
                update_token_usage(self._usage, raw_usage)
                return


class KimiModel(StandardOpenAICompatibleModel):
    def __init__(self, *, model_perf: str, api_key: str, base_url: str | None = None):
        super().__init__(
            model_perf=model_perf,
            provider_name="kimi",
            api_key=api_key,
            base_url=base_url,
        )

    def _build_completion_params(
        self,
        *,
        model_settings: ModelSettings,
        stream: bool,
        schema: type[BaseModel] | None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "max_completion_tokens": model_settings.max_tokens,
        }
        params.update(self._sampling_params(model_settings))
        params.update(self._thinking_params(model_settings))
        if stream:
            params.update(self._stream_params())
        if schema is not None:
            params["response_format"] = self._json_schema_format(schema)
        return params

    def _sampling_params(self, model_settings: ModelSettings) -> dict[str, Any]:
        model = self._model.lower()
        if model.startswith(("kimi-k2.5", "kimi-k2.6", "kimi-k2.7", "kimi-k3")):
            # Kimi 思考模型使用固定采样配置，显式传入会被拒绝。
            return {}
        return {
            "temperature": model_settings.temperature,
            "top_p": model_settings.top_p,
        }

    def _thinking_params(self, model_settings: ModelSettings) -> dict[str, Any]:
        thinking = model_settings.thinking
        model = self._model.lower()
        params: dict[str, Any] = {}

        if model.startswith("kimi-k3"):
            if thinking is not False:
                level = "max" if thinking is True else thinking
                level_map = {
                    "minimal": "low",
                    "low": "low",
                    "medium": "high",
                    "high": "high",
                    "xhigh": "max",
                    "max": "max",
                }
                params["reasoning_effort"] = level_map[level]
        elif model.startswith(("kimi-k2.5", "kimi-k2.6")):
            params["extra_body"] = {
                "thinking": {"type": "disabled" if thinking is False else "enabled"}
            }
        return params

    def _stream_params(self) -> dict[str, Any]:
        return {"stream_options": {"include_usage": True}}

    def _to_streamed_response(
        self,
        stream: AsyncStream[ChatCompletionChunk],
    ) -> KimiStreamedResponse:
        return KimiStreamedResponse(stream)
