"""Provider adapter 创建入口。"""

from typing import Protocol

from app.db.schemas import ProviderWithModelInternalRead

from .base import StructuredCompleter, TextCompleter


class FullCompleter(TextCompleter, StructuredCompleter, Protocol):
    """同时支持流式文本生成和结构化输出的 Completer 接口。"""

    ...


def completer_factory(
    provider_with_model: ProviderWithModelInternalRead,
) -> FullCompleter:
    """根据 Provider 与模型配置创建对应的 adapter。"""
    provider = provider_with_model.name
    model = provider_with_model.model_profile.model
    api_key = (
        provider_with_model.api_key.get_secret_value()
        if provider_with_model.api_key
        else None
    )

    if provider == "google":
        from .adapters.gemini import GeminiModel

        if api_key is None:
            raise ValueError("API key is required for Gemini provider.")
        return GeminiModel(
            model_perf=model,
            api_key=api_key,
            base_url=provider_with_model.base_url,
        )

    if provider == "anthropic":
        from .adapters.anthropic import AnthropicModel

        if api_key is None:
            raise ValueError("API key is required for Anthropic provider.")
        return AnthropicModel(
            model_perf=model,
            api_key=api_key,
            base_url=provider_with_model.base_url,
        )

    if provider == "openai":
        from .adapters.openai_compatible.openai import OpenAIModel

        if api_key is None:
            raise ValueError("API key is required for OpenAI provider.")
        return OpenAIModel(
            model_perf=model,
            api_key=api_key,
            base_url=provider_with_model.base_url,
        )

    if provider == "deepseek":
        from .adapters.openai_compatible.deepseek import DeepSeekModel

        if api_key is None:
            raise ValueError("API key is required for DeepSeek provider.")
        return DeepSeekModel(
            model_perf=model,
            api_key=api_key,
            base_url=provider_with_model.base_url,
        )

    if provider == "kimi":
        from .adapters.openai_compatible.kimi import KimiModel

        if api_key is None:
            raise ValueError("API key is required for Kimi provider.")
        return KimiModel(
            model_perf=model,
            api_key=api_key,
            base_url=provider_with_model.base_url,
        )

    if provider in {"alibaba", "alibaba-cn"}:
        from .adapters.openai_compatible.alibaba import AlibabaModel

        if api_key is None:
            raise ValueError("API key is required for Alibaba provider.")
        return AlibabaModel(
            model_perf=model,
            provider_name=provider,
            api_key=api_key,
            base_url=provider_with_model.base_url,
        )

    if provider in {"minimax", "minimax-cn"}:
        from .adapters.openai_compatible.minimax import MiniMaxModel

        if api_key is None:
            raise ValueError("API key is required for MiniMax provider.")
        return MiniMaxModel(
            model_perf=model,
            provider_name=provider,
            api_key=api_key,
            base_url=provider_with_model.base_url,
        )

    if provider == "glm":
        from .adapters.openai_compatible.glm import GLMModel

        if api_key is None:
            raise ValueError("API key is required for GLM provider.")
        return GLMModel(
            model_perf=model,
            api_key=api_key,
            base_url=provider_with_model.base_url,
        )

    if provider == "groq":
        from .adapters.openai_compatible.groq import GroqModel

        if api_key is None:
            raise ValueError("API key is required for Groq provider.")
        return GroqModel(
            model_perf=model,
            api_key=api_key,
            base_url=provider_with_model.base_url,
        )

    from .adapters.openai_compatible.standard import StandardOpenAICompatibleModel

    if provider == "ollama":
        return StandardOpenAICompatibleModel(
            model_perf=model,
            provider_name="ollama",
            api_key=api_key or "ollama",
            base_url=provider_with_model.base_url or "http://localhost:11434",
        )

    if api_key is None:
        raise ValueError(f"API key is required for custom provider {provider}.")
    if not provider_with_model.base_url:
        raise ValueError(f"Base URL is required for custom provider {provider}.")

    return StandardOpenAICompatibleModel(
        model_perf=model,
        provider_name=provider,
        api_key=api_key,
        base_url=provider_with_model.base_url,
    )
