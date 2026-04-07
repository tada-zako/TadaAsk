from typing import Any

from .base import Model
from .gemini import GeminiModel
from app.core.config import settings

__all__ = [
    "Model",
    "GeminiModel",
]


def model_factory(
    provider: str | None = None,
    model: str | None = None,
) -> Model[Any]:
    """
    model 工厂，根据 provider 返回对应的 Model 实例。
    NOTE: 目前仅支持 GeminiModel。
    """
    provider = (provider or settings.llm_provider_perf or "google").lower()

    if provider == "google":
        return GeminiModel(model_perf=model)
    raise ValueError(f"Unsupported LLM provider: {provider}")
