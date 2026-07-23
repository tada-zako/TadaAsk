"""Kimi 官方 Provider。"""

from typing import Any

from openai import omit
from openai.types.chat import ChatCompletionChunk

from ...base import ModelSettings, TokenUsage
from .base import OpenAICompatibleModel, _update_token_usage


class KimiModel(OpenAICompatibleModel):
    def __init__(self, *, model_perf: str, api_key: str, base_url: str | None = None):
        super().__init__(
            model_perf=model_perf,
            provider_name="kimi",
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
                kwargs["reasoning_effort"] = level_map[level]
        elif model.startswith(("kimi-k2.5", "kimi-k2.6")):
            kwargs["extra_body"] = {
                "thinking": {
                    "type": "disabled" if thinking is False else "enabled"
                }
            }

        if model.startswith(("kimi-k2.5", "kimi-k2.6", "kimi-k2.7", "kimi-k3")):
            # Kimi 思考模型使用固定采样配置，显式传入会被拒绝。
            kwargs["temperature"] = omit
            kwargs["top_p"] = omit
        if stream:
            kwargs["stream_options"] = {"include_usage": True}
        return kwargs

    def _update_stream_usage(
        self,
        chunk: ChatCompletionChunk,
        usage: TokenUsage,
    ) -> None:
        if chunk.usage is not None:
            _update_token_usage(usage, chunk.usage)
            return
        for choice in chunk.choices:
            raw_usage = getattr(choice, "usage", None)
            if raw_usage is not None:
                _update_token_usage(usage, raw_usage)
                return
