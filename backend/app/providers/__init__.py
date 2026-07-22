from typing import Protocol

from app.db.schemas import ProviderWithModelInternalRead
from .official import OFFICIAL_PROVIDER_BY_NAME
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
    CITATION_MARKER_TEMPLATE,
    DEFAULT_SYSTEM_PROMPT,
    QUERY_EXPAND_SYSTEM_PROMPT,
    QUERY_EXPAND_USER_TEMPLATE,
    STANDALONE_QUERY_REWRITE_PROMPT,
    SUMMARIZATION_PROMPT,
    UPDATE_SUMMARIZATION_PROMPT,
    TITLE_GENERATION_PROMPT,
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
    "CITATION_MARKER_TEMPLATE",
    "DEFAULT_SYSTEM_PROMPT",
    "QUERY_EXPAND_SYSTEM_PROMPT",
    "QUERY_EXPAND_USER_TEMPLATE",
    "STANDALONE_QUERY_REWRITE_PROMPT",
    "SUMMARIZATION_PROMPT",
    "UPDATE_SUMMARIZATION_PROMPT",
    "TITLE_GENERATION_PROMPT",
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

    provider_definition = OFFICIAL_PROVIDER_BY_NAME.get(provider)

    if provider == "google":
        from .gemini import GeminiModel

        if api_key is None:
            raise ValueError("API key is required for Gemini provider.")

        return GeminiModel(
            model_perf=model,
            api_key=api_key,
            base_url=provider_with_model.base_url,
        )

    elif provider_definition and provider_definition.protocol == "anthropic":
        from .anthropic import AnthropicModel

        if api_key is None:
            raise ValueError("API key is required for Anthropic provider.")

        return AnthropicModel(
            model_perf=model,
            api_key=api_key,
            base_url=provider_with_model.base_url,
        )

    elif provider_definition and provider_definition.protocol == "openai_compatible":
        from .openai_compatible import OpenAIChatModel, OpenAIEndpoint

        if api_key is None:
            raise ValueError(f"API key is required for {provider} provider.")

        endpoint = OpenAIEndpoint.official(
            endpoint_name=provider_definition.name,
            api_key=api_key,
            base_url=provider_with_model.base_url or provider_definition.base_url,
            supports_reasoning_effort=provider_definition.supports_reasoning_effort,
            supports_stream_usage=provider_definition.supports_stream_usage,
        )

        return OpenAIChatModel(model_perf=model, endpoint=endpoint)

    elif provider == "ollama":
        from .openai_compatible import OpenAIChatModel, OpenAIEndpoint

        endpoint = OpenAIEndpoint.ollama(
            api_key=api_key,
            base_url=provider_with_model.base_url,
        )

        return OpenAIChatModel(model_perf=model, endpoint=endpoint)

    else:
        # custom provider
        from .openai_compatible import OpenAIChatModel, OpenAIEndpoint

        if api_key is None:
            raise ValueError(f"API key is required for custom provider {provider}.")
        if not provider_with_model.base_url:
            raise ValueError(f"Base URL is required for custom provider {provider}.")

        endpoint = OpenAIEndpoint.custom(
            endpoint_name=provider,
            api_key=api_key,
            base_url=provider_with_model.base_url,
        )

        return OpenAIChatModel(model_perf=model, endpoint=endpoint)
