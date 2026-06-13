from typing import Protocol

from .base import (
    Message,
    StreamedResponse,
    TextCompleter,
    StructuredCompleter,
    ThinkingLevel,
    ModelSettings,
)
from .prompts import (
    DEFAULT_SYSTEM_PROMPT,
    QUERY_EXPAND_SYSTEM_PROMPT,
    QUERY_EXPAND_USER_TEMPLATE,
    STANDALONE_QUERY_REWRITE_PROMPT,
)

__all__ = [
    "Message",
    "ThinkingLevel",
    "ModelSettings",
    "StreamedResponse",
    "TextCompleter",
    "StructuredCompleter",
    "DEFAULT_SYSTEM_PROMPT",
    "QUERY_EXPAND_SYSTEM_PROMPT",
    "QUERY_EXPAND_USER_TEMPLATE",
    "STANDALONE_QUERY_REWRITE_PROMPT",
]


class FullCompleter(TextCompleter, StructuredCompleter, Protocol):
    """同时支持流式文本生成和结构化输出的 Completer 接口"""

    ...


def completer_factory(
    provider: str,
    model: str,
) -> FullCompleter:
    """ """
    if provider == "google":
        from .gemini import GeminiModel

        return GeminiModel(model_perf=model)

    elif provider in ("openai", "deepseek", "ollama"):
        from .openai_compatible import OpenAIChatModel, OpenAIEndpoint

        endpoint_map = {
            "openai": OpenAIEndpoint.openai,
            "deepseek": OpenAIEndpoint.deepseek,
            "ollama": OpenAIEndpoint.ollama,
        }
        endpoint = endpoint_map[provider]()
        return OpenAIChatModel(model_perf=model, endpoint=endpoint)

    raise ValueError(f"Unsupported TextCompleter provider: {provider}")
