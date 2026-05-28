from .chromadb import VectorQueryResult, VectorDatabase, ChromaDB
from .text_splitter import (
    TextChunk,
    TextSplitter,
    TokenAwareTextSplitter,
    ASTAwareTextSplitter,
)
from .embedding import EmbeddingProvider
from .utils.tokenizer import TokenizerBase
from .rerank import RerankProvider
from .query_expand import QueryExpander, ExpandedQuery
from .fts import FTSProvider
from app.core.config import EmbeddingBackend

__all__ = [
    "VectorQueryResult",
    "VectorDatabase",
    "ChromaDB",
    "TextChunk",
    "TextSplitter",
    "TokenAwareTextSplitter",
    "ASTAwareTextSplitter",
    "EmbeddingProvider",
    "TokenizerBase",
    "RerankProvider",
    "QueryExpander",
    "ExpandedQuery",
    "FTSProvider",
]


def vector_db_factory(
    vector_store: str,
) -> VectorDatabase:
    """
    向量库工厂函数，根据配置返回对应的 VectorDatabase 实例。
    NOTE: 目前仅支持 ChromaDB。
    """
    if vector_store == "chromadb":
        return ChromaDB()
    raise ValueError(f"Unsupported vector store provider: {vector_store}")


def embedding_provider_factory(
    embedding_mode: EmbeddingBackend, model_name: str, cache_dir: str | None = None
) -> EmbeddingProvider:
    """
    向量化服务工厂函数，根据配置返回对应的 EmbeddingProvider 实例。
    NOTE: 目前仅支持 FastEmbeddingAdapter（基于 HuggingFace 模型的适配器）。
    """
    if embedding_mode == "fastembed":
        from .embedding import FastEmbeddingAdapter

        return FastEmbeddingAdapter(
            model_name=model_name,
            cache_dir=cache_dir,
        )
    raise ValueError(f"Unsupported embedding provider: {embedding_mode}")
