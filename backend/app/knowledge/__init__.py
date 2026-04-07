from .base import VectorQueryItem, VectorDatabase
from .chromadb import ChromaDB
from app.core.config import settings

__all__ = ["VectorQueryItem", "VectorDatabase", "ChromaDB"]


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
