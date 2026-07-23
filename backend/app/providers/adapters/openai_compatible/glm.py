"""智谱 GLM 官方 Provider。"""

from typing import Any

from pydantic import BaseModel

from ...base import ModelSettings
from .standard import StandardOpenAICompatibleModel


class GLMModel(StandardOpenAICompatibleModel):
    def __init__(self, *, model_perf: str, api_key: str, base_url: str | None = None):
        super().__init__(
            model_perf=model_perf,
            provider_name="glm",
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
        del stream
        params: dict[str, Any] = {
            "temperature": model_settings.temperature,
            "top_p": model_settings.top_p,
            "max_tokens": model_settings.max_tokens,
        }
        params.update(self._thinking_params(model_settings))
        if schema is not None:
            params["response_format"] = self._json_object_format()
        return params

    def _thinking_params(self, model_settings: ModelSettings) -> dict[str, Any]:
        thinking = model_settings.thinking
        params: dict[str, Any] = {
            "extra_body": {
                "thinking": {"type": "disabled" if thinking is False else "enabled"}
            }
        }
        if self._model.lower().startswith("glm-5.2") and thinking is not False:
            params["reasoning_effort"] = "max" if thinking is True else thinking
        return params
