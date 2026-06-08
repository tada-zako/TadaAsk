from typing import Protocol

from fastembed import TextEmbedding
from numpy.typing import NDArray
import numpy as np

from app.utils import TTLCache, normalize_text, stable_hash


class EmbeddingProvider(Protocol):
    """文档嵌入协议"""

    def embed_documents(self, documents: list[str]) -> list[NDArray[np.float32]]:
        """将文本列表转换为嵌入向量列表

        Args:
            documents (list[str]): 待转换的文本列表

        Returns:
            list[NDArray[np.float32]]: 转换后的嵌入向量列表
        """
        ...

    def embed_query(self, query: str) -> NDArray[np.float32]:
        """将查询文本转换为嵌入向量

        Args:
            query (str): 待转换的查询文本

        Returns:
            NDArray[np.float32]: 转换后的查询嵌入向量
        """
        ...


class FastEmbeddingAdapter:
    """基于 fastembed 的文本嵌入适配器"""

    def __init__(
        self,
        model_name: str,
        cache_dir: str | None = None,
        *,
        cache_enabled: bool = True,
        cache_size: int = 1024,
        ttl_seconds: int = 1800,
    ):
        self._model_name = self._map_hf_to_fastembed(model_name)
        self._cache_dir = cache_dir
        self._cache_enabled = cache_enabled

        if self._cache_enabled:
            # TTL Cache 缓存嵌入结果：文本 -> 向量
            self._cache = TTLCache[str, NDArray[np.float32]](
                max_size=cache_size, ttl_seconds=ttl_seconds
            )

        self.embedding = TextEmbedding(
            model_name=self._model_name, cache_dir=self._cache_dir
        )

    def _cache_key(self, text: str) -> str:
        """生成缓存键；基于文本的规范化和稳定哈希"""
        return stable_hash(
            {
                "kind": "query_embedding",
                "model": self._model_name,  # 模型名称确定不同的嵌入结果
                "text": normalize_text(text),
            }
        )

    def _map_hf_to_fastembed(self, model_name: str) -> str:
        """
        将 HuggingFace 模型名称映射为 fastembed 内部名称
        """
        # 未传入模型名称，使用默认
        if not model_name:
            return "BAAI/bge-small-en-v1.5"

        hf_to_fastembed = {
            info["sources"]["hf"]: info["model"]
            for info in TextEmbedding.list_supported_models()
            if info["sources"].get("hf")
        }
        if model_name in hf_to_fastembed:
            return hf_to_fastembed[model_name]
        else:
            # 如果没有映射关系，直接返回原名称，交由 fastembed 内部处理
            return model_name

    def embed_documents(self, documents: list[str]) -> list[NDArray[np.float32]]:
        """将文档列表转换为嵌入向量列表"""
        # 长文档不设置缓存
        return [e.astype(np.float32) for e in self.embedding.embed(documents)]

    def embed_query(self, query: str) -> NDArray[np.float32]:
        """将查询文本转换为嵌入向量"""
        if self._cache_enabled:
            # 检查缓存结果
            key = self._cache_key(query)
            cached_embedding = self._cache.get(key)
            if cached_embedding is not None:
                return cached_embedding.copy()

        try:
            first_item = next(iter(self.embedding.query_embed([query])))
            result = first_item.astype(np.float32)
        except StopIteration:
            result = np.array([], dtype=np.float32)

        # 设置缓存结果
        if self._cache_enabled:
            self._cache.set(key, result.copy())  # type: ignore

        return result
