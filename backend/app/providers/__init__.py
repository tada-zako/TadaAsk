from typing import Protocol

from app.db.schemas import ProviderWithModelInternalRead
from .base import (
    Message,
    StreamedResponse,
    TextCompleter,
    StructuredCompleter,
    ThinkingLevel,
    ModelSettings,
    TokenUsage,
    ModelResponse,
)
from .prompts import (
    DEFAULT_SYSTEM_PROMPT,
    QUERY_EXPAND_SYSTEM_PROMPT,
    QUERY_EXPAND_USER_TEMPLATE,
    STANDALONE_QUERY_REWRITE_PROMPT,
    SUMMARIZATION_PROMPT,
    UPDATE_SUMMARIZATION_PROMPT,
)


__all__ = [
    "Message",
    "ThinkingLevel",
    "ModelSettings",
    "TokenUsage",
    "ModelResponse",
    "StreamedResponse",
    "TextCompleter",
    "StructuredCompleter",
    "DEFAULT_SYSTEM_PROMPT",
    "QUERY_EXPAND_SYSTEM_PROMPT",
    "QUERY_EXPAND_USER_TEMPLATE",
    "STANDALONE_QUERY_REWRITE_PROMPT",
    "SUMMARIZATION_PROMPT",
    "UPDATE_SUMMARIZATION_PROMPT",
]


class FullCompleter(TextCompleter, StructuredCompleter, Protocol):
    """同时支持流式文本生成和结构化输出的 Completer 接口"""

    ...


def completer_factory(
    provider_with_model: ProviderWithModelInternalRead,
) -> FullCompleter:
    """FullCompleter 工厂函数"""
    # 预备参数
    provider = provider_with_model.name
    model = provider_with_model.model_profile.model

    api_key = None
    if provider_with_model.api_key:
        api_key = provider_with_model.api_key.get_secret_value()

    if provider == "google":
        from .gemini import GeminiModel

        if api_key is None:
            raise ValueError("API key is required for Gemini provider.")

        return GeminiModel(
            model_perf=model,
            api_key=api_key,
            base_url=provider_with_model.base_url,
        )

    elif provider in ("openai", "deepseek", "ollama"):
        from .openai_compatible import OpenAIChatModel, OpenAIEndpoint

        if provider != "ollama" and api_key is None:
            raise ValueError(f"API key is required for {provider} provider.")

        endpoint_map = {
            "openai": OpenAIEndpoint.openai,
            "deepseek": OpenAIEndpoint.deepseek,
            "ollama": OpenAIEndpoint.ollama,
        }
        endpoint = endpoint_map[provider](
            api_key=api_key,
            base_url=provider_with_model.base_url,
        )

        return OpenAIChatModel(model_perf=model, endpoint=endpoint)

    raise ValueError(f"Unsupported TextCompleter provider: {provider}")
