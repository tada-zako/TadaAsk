from typing import Any

from .base import Message, StreamedResponse, TextCompleter, StructuredCompleter
from .gemini import GeminiModel
from .prompts import (
    DEFAULT_SYSTEM_PROMPT,
    QUERY_EXPAND_SYSTEM_PROMPT,
    QUERY_EXPAND_USER_TEMPLATE,
)

__all__ = [
    "Message",
    "StreamedResponse",
    "TextCompleter",
    "StructuredCompleter",
    "GeminiModel",
    "DEFAULT_SYSTEM_PROMPT",
    "QUERY_EXPAND_SYSTEM_PROMPT",
    "QUERY_EXPAND_USER_TEMPLATE",
]


def model_factory(
    provider: str | None = None,
    model: str | None = None,
) -> Model[Any]:
    """
    model 工厂，根据 provider 返回对应的 Model 实例。
    NOTE: 目前仅支持 GeminiModel。
    """
    if provider == "google":
        return GeminiModel(model_perf=model)
    raise ValueError(f"Unsupported LLM provider: {provider}")
