"""Alibaba Model Studio 官方 Provider。"""

from typing import Any

from .base import ModelSettings
from .openai_compatible import OpenAICompatibleModel


class AlibabaModel(OpenAICompatibleModel):
    def __init__(
        self,
        *,
        model_perf: str,
        provider_name: str,
        api_key: str,
        base_url: str | None = None,
    ):
        super().__init__(
            model_perf=model_perf,
            provider_name=provider_name,
            api_key=api_key,
            base_url=base_url,
        )

    def _provider_request_kwargs(
        self,
        model_settings: ModelSettings,
        *,
        stream: bool,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "extra_body": {"enable_thinking": model_settings.thinking is not False}
        }
        if stream:
            kwargs["stream_options"] = {"include_usage": True}
        return kwargs

    def _map_json_schema(self, schema):
        return self._map_json_object(schema)
