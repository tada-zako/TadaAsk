from .calcu_file_hash import calculate_file_hash
from .ttl_cache import TTLCache
from .cache_keys import normalize_text, stable_hash
from .gen_collection_name import generate_collection_name
from .tokenizer import EmbeddingTokenizer
from app.core.config import EmbeddingBackend


__all__ = [
    "calculate_file_hash",
    "TTLCache",
    "normalize_text",
    "stable_hash",
    "generate_collection_name",
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
