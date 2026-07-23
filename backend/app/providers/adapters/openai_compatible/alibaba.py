"""Alibaba Model Studio 官方 Provider。"""

from typing import Any

from pydantic import BaseModel

from ...base import ModelSettings
from .standard import StandardOpenAICompatibleModel


class AlibabaModel(StandardOpenAICompatibleModel):
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
            "max_completion_tokens": model_settings.max_tokens,
        }
        params.update(self._thinking_params(model_settings))
        if stream:
            params.update(self._stream_params())
        if schema is not None:
            params["response_format"] = self._json_object_format()
        return params

    def _thinking_params(self, model_settings: ModelSettings) -> dict[str, Any]:
        return {"extra_body": {"enable_thinking": model_settings.thinking is not False}}

    def _stream_params(self) -> dict[str, Any]:
        return {"stream_options": {"include_usage": True}}
