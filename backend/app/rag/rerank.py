import math
from typing import Protocol

from fastembed.rerank.cross_encoder import TextCrossEncoder


class RerankProvider(Protocol):
    """Rerank 协议"""

    def rerank(self, query: str, documents: list[str]) -> list[float]:
        """对文档嵌入进行 Rerank，返回 0~1 的相关度分数列表

        Args:
            query (str): 查询文本
            documents (list[str]): 待 Rerank 的文档列表

        Returns:
            list[float]: 与查询的相关度分数列表，长度与 documents 相同，分数越高越相关
        """
        ...


class FastRerankAdapter:
    """基于 fastembed 的 Rerank 适配器"""

    def __init__(self, model_name: str, cache_dir: str | None = None):
        self._model_name = self._map_hf_to_fastembed(model_name)
        self._cache_dir = cache_dir

        self.reranker = TextCrossEncoder(
            model_name=self._model_name, cache_dir=self._cache_dir
        )

    def _map_hf_to_fastembed(self, model_name: str) -> str:
        """
        将 HuggingFace 模型名称映射为 fastembed 内部名称
        """
        # 未传入模型名称，使用默认
        if not model_name:
            return "jinaai/jina-reranker-v2-base-multilingual"

        # fastembed rerank 模型不需要进行映射
        return model_name

    @staticmethod
    def _normalize_score(raw_score: float) -> float:
        """将 fastembed cross-encoder 原始分数转成可阈值判断的 0~1 分数。"""
        score = float(raw_score)
        if score >= 0:
            z = math.exp(-score)
            return 1 / (1 + z)

        z = math.exp(score)
        return z / (1 + z)

    def rerank(self, query: str, documents: list[str]) -> list[float]:
        """使用 fastembed 的 TextCrossEncoder 对文档嵌入进行 Rerank"""
        raw_scores = self.reranker.rerank(query, documents)
        return [self._normalize_score(score) for score in raw_scores]
