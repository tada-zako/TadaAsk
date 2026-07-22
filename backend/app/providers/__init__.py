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

    if provider == "google":
        from .gemini import GeminiModel

        if api_key is None:
            raise ValueError("API key is required for Gemini provider.")

        return GeminiModel(
            model_perf=model,
            api_key=api_key,
            base_url=provider_with_model.base_url,
        )

    elif provider == "anthropic":
        from .anthropic import AnthropicModel

        if api_key is None:
            raise ValueError("API key is required for Anthropic provider.")

        return AnthropicModel(
            model_perf=model,
            api_key=api_key,
            base_url=provider_with_model.base_url,
        )

    elif provider == "openai":
        from .openai import OpenAIModel

        if api_key is None:
            raise ValueError("API key is required for OpenAI provider.")
        return OpenAIModel(
            model_perf=model,
            api_key=api_key,
            base_url=provider_with_model.base_url,
        )

    elif provider == "deepseek":
        from .deepseek import DeepSeekModel

        if api_key is None:
            raise ValueError("API key is required for DeepSeek provider.")
        return DeepSeekModel(
            model_perf=model,
            api_key=api_key,
            base_url=provider_with_model.base_url,
        )

    elif provider == "kimi":
        from .kimi import KimiModel

        if api_key is None:
            raise ValueError("API key is required for Kimi provider.")
        return KimiModel(
            model_perf=model,
            api_key=api_key,
            base_url=provider_with_model.base_url,
        )

    elif provider in {"alibaba", "alibaba-cn"}:
        from .alibaba import AlibabaModel

        if api_key is None:
            raise ValueError("API key is required for Alibaba provider.")
        return AlibabaModel(
            model_perf=model,
            provider_name=provider,
            api_key=api_key,
            base_url=provider_with_model.base_url,
        )

    elif provider in {"minimax", "minimax-cn"}:
        from .minimax import MiniMaxModel

        if api_key is None:
            raise ValueError("API key is required for MiniMax provider.")
        return MiniMaxModel(
            model_perf=model,
            provider_name=provider,
            api_key=api_key,
            base_url=provider_with_model.base_url,
        )

    elif provider == "glm":
        from .glm import GLMModel

        if api_key is None:
            raise ValueError("API key is required for GLM provider.")
        return GLMModel(
            model_perf=model,
            api_key=api_key,
            base_url=provider_with_model.base_url,
        )

    elif provider == "groq":
        from .groq import GroqModel

        if api_key is None:
            raise ValueError("API key is required for Groq provider.")
        return GroqModel(
            model_perf=model,
            api_key=api_key,
            base_url=provider_with_model.base_url,
        )

    elif provider == "ollama":
        from .openai_compatible import OpenAICompatibleModel

        return OpenAICompatibleModel(
            model_perf=model,
            provider_name="ollama",
            api_key=api_key or "ollama",
            base_url=provider_with_model.base_url or "http://localhost:11434",
        )

    else:
        # custom provider
        from .openai_compatible import OpenAICompatibleModel

        if api_key is None:
            raise ValueError(f"API key is required for custom provider {provider}.")
        if not provider_with_model.base_url:
            raise ValueError(f"Base URL is required for custom provider {provider}.")

        return OpenAICompatibleModel(
            model_perf=model,
            provider_name=provider,
            api_key=api_key,
            base_url=provider_with_model.base_url,
        )
