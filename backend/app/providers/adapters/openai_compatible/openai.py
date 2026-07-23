"""OpenAI 官方 Provider。"""

from typing import Any

from ...base import ModelSettings
from .base import OpenAICompatibleModel


class OpenAIModel(OpenAICompatibleModel):
    def __init__(self, *, model_perf: str, api_key: str, base_url: str | None = None):
        super().__init__(
            model_perf=model_perf,
            provider_name="openai",
            api_key=api_key,
            base_url=base_url,
        )

    def _use_developer_role(self) -> bool:
        return True

    def _provider_request_kwargs(
        self,
        model_settings: ModelSettings,
        *,
        stream: bool,
    ) -> dict[str, Any]:
        level = "medium" if model_settings.thinking is True else model_settings.thinking
        kwargs: dict[str, Any] = {}
        if level is not False:
            kwargs["reasoning_effort"] = level
        if stream:
            kwargs["stream_options"] = {"include_usage": True}
        return kwargs
