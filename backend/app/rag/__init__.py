from .chromadb import VectorQueryResult, VectorDatabase, ChromaDB
from .text_splitter import (
    TextChunk,
    TextSplitter,
    TokenAwareTextSplitter,
    ASTAwareTextSplitter,
)
from .embedding import EmbeddingProvider, FastEmbeddingAdapter
from .utils.tokenizer import TokenizerBase, HuggingFaceTokenizer
from .rerank import RerankProvider, FastRerankAdapter
from .query_expand import QueryExpander, ExpandedQuery
from app.core.config import settings

__all__ = [
    "VectorQueryResult",
    "VectorDatabase",
    "ChromaDB",
    "TextChunk",
    "TextSplitter",
    "TokenAwareTextSplitter",
    "ASTAwareTextSplitter",
    "EmbeddingProvider",
    "FastEmbeddingAdapter",
    "TokenizerBase",
    "HuggingFaceTokenizer",
    "RerankProvider",
    "FastRerankAdapter",
    "QueryExpander",
    "ExpandedQuery",
]


def vector_db_factory(
    vector_store: str | None = None,
) -> VectorDatabase:
    """
    向量库工厂函数，根据配置返回对应的 VectorDatabase 实例。
    NOTE: 目前仅支持 ChromaDB。
    """
    v_name = (vector_store or settings.vector_store_perf or "chromadb").lower()

    if v_name == "chromadb":
        return ChromaDB()
    raise ValueError(f"Unsupported vector store provider: {v_name}")
