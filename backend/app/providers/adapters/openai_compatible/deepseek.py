"""DeepSeek 官方 Provider。"""

from typing import Any

from pydantic import BaseModel

from ...base import ModelSettings
from .standard import StandardOpenAICompatibleModel


class DeepSeekModel(StandardOpenAICompatibleModel):
    def __init__(self, *, model_perf: str, api_key: str, base_url: str | None = None):
        super().__init__(
            model_perf=model_perf,
            provider_name="deepseek",
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
            "temperature": model_settings.temperature,
            "top_p": model_settings.top_p,
            "max_tokens": model_settings.max_tokens,
        }
        params.update(self._thinking_params(model_settings))
        if stream:
            params.update(self._stream_params())
        if schema is not None:
            params["response_format"] = self._json_object_format()
        return params

    def _thinking_params(self, model_settings: ModelSettings) -> dict[str, Any]:
        thinking = model_settings.thinking
        extra_body: dict[str, Any] = {
            "thinking": {"type": "disabled" if thinking is False else "enabled"}
        }
        params: dict[str, Any] = {"extra_body": extra_body}

        if thinking is not False:
            level = "high" if thinking is True else thinking
            level_map = {
                "minimal": "high",
                "low": "high",
                "medium": "high",
                "high": "high",
                "xhigh": "max",
                "max": "max",
            }
            params["reasoning_effort"] = level_map[level]
        return params

    def _stream_params(self) -> dict[str, Any]:
        return {"stream_options": {"include_usage": True}}
