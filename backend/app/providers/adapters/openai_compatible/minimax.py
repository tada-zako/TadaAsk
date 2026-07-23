"""MiniMax 官方 Provider。"""

from typing import Any

from ...base import ModelSettings
from .base import OpenAICompatibleModel, StreamContentReader


class MiniMaxModel(OpenAICompatibleModel):
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
        del model_settings
        kwargs: dict[str, Any] = {
            "extra_body": {"reasoning_split": True},
        }
        if stream:
            kwargs["stream_options"] = {"include_usage": True}
        return kwargs

    def _stream_content_reader(self) -> StreamContentReader:
        # MiniMax OpenAI-compatible 流可能返回累计文本，在单次响应内转换为增量。
        previous = ""

        def read_content(chunk):
            nonlocal previous
            content = self._read_stream_content(chunk)
            if not content:
                return None
            if content.startswith(previous):
                incremental = content[len(previous) :]
                previous = content
                return incremental or None
            previous += content
            return content

        return read_content
