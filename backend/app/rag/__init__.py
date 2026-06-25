from .chromadb import VectorQueryResult, VectorDatabase
from .text_splitter import (
    TextChunk,
    TextSplitter,
    TokenAwareTextSplitter,
    ASTAwareTextSplitter,
)
from .embedding import EmbeddingProvider
from .rerank import RerankProvider
from .query_expand import QueryExpander, ExpandedQuery
from .fts import FTSProvider, SQLiteFTSProvider, FTSResult
from .standalone_rewriter import StandaloneQueryRewriter
from app.core.config import Settings

__all__ = [
    "VectorQueryResult",
    "VectorDatabase",
    "TextChunk",
    "TextSplitter",
    "TokenAwareTextSplitter",
    "ASTAwareTextSplitter",
    "EmbeddingProvider",
    "RerankProvider",
    "QueryExpander",
    "ExpandedQuery",
    "FTSResult",
    "FTSProvider",
    "SQLiteFTSProvider",
    "StandaloneQueryRewriter",
]


def vector_db_factory(
    vector_store: str,
) -> VectorDatabase:
    """
    向量库工厂函数，根据配置返回对应的 VectorDatabase 实例。
    NOTE: 目前仅支持 ChromaDB。
    """
    if vector_store == "chromadb":
        from .chromadb import ChromaDB

        return ChromaDB()
    raise ValueError(f"Unsupported vector store provider: {vector_store}")


def embedding_provider_factory(settings: Settings) -> EmbeddingProvider:
    """
    向量化服务工厂函数，根据配置返回对应的 EmbeddingProvider 实例。
    NOTE: 目前仅支持 FastEmbeddingAdapter（基于 HuggingFace 模型的适配器）。
    NOTE: 该工厂函数传递 Settings 对象，是由于 FastEmbedding
            和 LlamaCppEmbedding 使用的cache_dir 配置项不同，
            不方便通过函数参数传递
    """
    if settings.embedding_backend == "fastembed":
        from .embedding import FastEmbeddingAdapter

        return FastEmbeddingAdapter(
            model_name=settings.embedding_model_name,
            cache_dir=settings.fastembed_model_cache_dir,
        )
    raise ValueError(f"Unsupported embedding provider: {settings.embedding_backend}")


def rerank_provider_factory(settings: Settings) -> RerankProvider:
    """
    Rerank 服务工厂函数，根据配置返回对应的 RerankProvider 实例。
    NOTE: 目前仅支持 FastRerankAdapter（基于 HuggingFace 模型的适配器）。
    """
    if settings.rerank_backend == "fastembed":
        from .rerank import FastRerankAdapter

        return FastRerankAdapter(
            model_name=settings.rerank_model_name,
            cache_dir=settings.fastembed_model_cache_dir,
        )
    raise ValueError(f"Unsupported rerank provider: {settings.rerank_backend}")
