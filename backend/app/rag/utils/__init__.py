from .breakpoint_scanner import (
    SupportedLanguages,
    MarkdownBreakpointScanner,
    ASTBreakpointScanner,
    Breakpoint,
)
from .code_fence_scanner import CodeFenceScanner, CodeFence
from .tokenizer import EmbeddingTokenizer
from .fts_tokenizer import FTSTokenizer, JiebaFTSTokenizer
from app.core.config import EmbeddingBackend


__all__ = [
    "Breakpoint",
    "CodeFence",
    "MarkdownBreakpointScanner",
    "SupportedLanguages",
    "ASTBreakpointScanner",
    "CodeFenceScanner",
    "EmbeddingTokenizer",
    "FTSTokenizer",
    "JiebaFTSTokenizer",
]


def embedding_tokenizer_factory(
    embedding_mode: EmbeddingBackend, model_name: str, cache_dir: str | None = None
) -> EmbeddingTokenizer:
    """
    Embedding Tokenizer 工厂函数，根据配置返回对应的 EmbeddingTokenizer 实例。
    NOTE: 目前仅支持 HuggingFaceTokenizer（基于 HuggingFace Hub 模型的适配器）。
    """
    if embedding_mode == "fastembed":
        from .tokenizer import HuggingFaceTokenizer

        return HuggingFaceTokenizer(
            model_name=model_name,
            cache_dir=cache_dir,
        )
    raise ValueError(f"Unsupported embedding tokenizer provider: {embedding_mode}")
