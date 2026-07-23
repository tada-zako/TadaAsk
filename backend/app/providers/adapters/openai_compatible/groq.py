"""Groq 官方 Provider。"""

from typing import Any

from ...base import ModelSettings
from .base import OpenAICompatibleModel


class GroqModel(OpenAICompatibleModel):
    def __init__(self, *, model_perf: str, api_key: str, base_url: str | None = None):
        super().__init__(
            model_perf=model_perf,
            provider_name="groq",
            api_key=api_key,
            base_url=base_url,
        )

    def _provider_request_kwargs(
        self,
        model_settings: ModelSettings,
        *,
        stream: bool,
    ) -> dict[str, Any]:
        thinking = model_settings.thinking
        model = self._model.lower()
        kwargs: dict[str, Any] = {}

        if "qwen" in model:
            kwargs["reasoning_effort"] = "none" if thinking is False else "default"
        elif "gpt-oss" in model and thinking is not False:
            level = "medium" if thinking is True else thinking
            if level in {"minimal", "low"}:
                kwargs["reasoning_effort"] = "low"
            elif level == "medium":
                kwargs["reasoning_effort"] = "medium"
            else:
                kwargs["reasoning_effort"] = "high"

        if stream:
            kwargs["stream_options"] = {"include_usage": True}
        return kwargs
