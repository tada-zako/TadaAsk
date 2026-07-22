"""DeepSeek 官方 Provider。"""

from typing import Any

from .base import ModelSettings
from .openai_compatible import OpenAICompatibleModel


class DeepSeekModel(OpenAICompatibleModel):
    def __init__(self, *, model_perf: str, api_key: str, base_url: str | None = None):
        super().__init__(
            model_perf=model_perf,
            provider_name="deepseek",
            api_key=api_key,
            base_url=base_url,
        )

    def _max_tokens_parameter(self) -> str:
        return "max_tokens"

    def _provider_request_kwargs(
        self,
        model_settings: ModelSettings,
        *,
        stream: bool,
    ) -> dict[str, Any]:
        thinking = model_settings.thinking
        extra_body: dict[str, Any] = {
            "thinking": {"type": "disabled" if thinking is False else "enabled"}
        }
        kwargs: dict[str, Any] = {"extra_body": extra_body}

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
            kwargs["reasoning_effort"] = level_map[level]
        if stream:
            kwargs["stream_options"] = {"include_usage": True}
        return kwargs

    def _map_json_schema(self, schema):
        return self._map_json_object(schema)
