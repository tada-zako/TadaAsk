"""Groq 官方 Provider。"""

from typing import Any

from pydantic import BaseModel

from ...base import ModelSettings
from .standard import StandardOpenAICompatibleModel


class GroqModel(StandardOpenAICompatibleModel):
    def __init__(self, *, model_perf: str, api_key: str, base_url: str | None = None):
        super().__init__(
            model_perf=model_perf,
            provider_name="groq",
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
        thinking = model_settings.thinking
        model = self._model.lower()
        params: dict[str, Any] = {}

        if "qwen" in model:
            params["reasoning_effort"] = "none" if thinking is False else "default"
        elif "gpt-oss" in model and thinking is not False:
            level = "medium" if thinking is True else thinking
            if level in {"minimal", "low"}:
                params["reasoning_effort"] = "low"
            elif level == "medium":
                params["reasoning_effort"] = "medium"
            else:
                params["reasoning_effort"] = "high"
        return params

    def _stream_params(self) -> dict[str, Any]:
        return {"stream_options": {"include_usage": True}}
