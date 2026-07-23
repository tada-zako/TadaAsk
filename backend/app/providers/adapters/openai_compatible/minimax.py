"""MiniMax 官方 Provider。"""

from typing import Any

from openai import AsyncStream
from openai.types.chat import ChatCompletionChunk
from pydantic import BaseModel

from ...base import ModelSettings
from .standard import StandardOpenAICompatibleModel, StandardOpenAIStreamedResponse


class MiniMaxStreamedResponse(StandardOpenAIStreamedResponse):
    """将 MiniMax 可能返回的累计文本转换为增量。"""

    def __init__(self, stream: AsyncStream[ChatCompletionChunk]) -> None:
        super().__init__(stream)
        self._previous_content = ""

    def _read_content(self, chunk: ChatCompletionChunk) -> str | None:
        content = super()._read_content(chunk)
        if not content:
            return None
        if content.startswith(self._previous_content):
            incremental = content[len(self._previous_content) :]
            self._previous_content = content
            return incremental or None
        self._previous_content += content
        return content


class MiniMaxModel(StandardOpenAICompatibleModel):
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
        params.update(self._reasoning_params())
        if stream:
            params.update(self._stream_params())
        if schema is not None:
            params["response_format"] = self._json_schema_format(schema)
        return params

    def _reasoning_params(self) -> dict[str, Any]:
        return {"extra_body": {"reasoning_split": True}}

    def _stream_params(self) -> dict[str, Any]:
        return {"stream_options": {"include_usage": True}}

    def _to_streamed_response(
        self,
        stream: AsyncStream[ChatCompletionChunk],
    ) -> MiniMaxStreamedResponse:
        return MiniMaxStreamedResponse(stream)
