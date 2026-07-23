"""智谱 GLM 官方 Provider。"""

from typing import Any

from ...base import ModelSettings
from .base import OpenAICompatibleModel


class GLMModel(OpenAICompatibleModel):
    def __init__(self, *, model_perf: str, api_key: str, base_url: str | None = None):
        super().__init__(
            model_perf=model_perf,
            provider_name="glm",
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
        del stream
        thinking = model_settings.thinking
        kwargs: dict[str, Any] = {
            "extra_body": {
                "thinking": {"type": "disabled" if thinking is False else "enabled"}
            }
        }
        if self._model.lower().startswith("glm-5.2") and thinking is not False:
            kwargs["reasoning_effort"] = "max" if thinking is True else thinking
        return kwargs

    def _map_json_schema(self, schema):
        return self._map_json_object(schema)
