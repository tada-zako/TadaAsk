from typing import Protocol

from fastembed import TextEmbedding
from numpy.typing import NDArray
import numpy as np


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

    def __init__(self, model_name: str, cache_dir: str | None = None):
        self._model_name = self._map_hf_to_fastembed(model_name)
        self._cache_dir = cache_dir

        self.embedding = TextEmbedding(
            model_name=self._model_name, cache_dir=self._cache_dir
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
        return [e.astype(np.float32) for e in self.embedding.embed(documents)]

    def embed_query(self, query: str) -> NDArray[np.float32]:
        """将查询文本转换为嵌入向量"""
        try:
            first_item = next(iter(self.embedding.query_embed([query])))
            return first_item.astype(np.float32)
        except StopIteration:
            # 处理空迭代器的情况
            return np.array([], dtype=np.float32)
