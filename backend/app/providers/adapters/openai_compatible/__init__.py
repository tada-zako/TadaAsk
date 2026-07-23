"""基于 OpenAI Chat Completions 协议的 Provider 适配器。"""

from .base import OpenAICompatibleModel
from .standard import StandardOpenAICompatibleModel

__all__ = ["OpenAICompatibleModel", "StandardOpenAICompatibleModel"]
