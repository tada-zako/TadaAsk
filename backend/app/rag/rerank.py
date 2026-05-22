from typing import Protocol

from fastembed.rerank.cross_encoder import TextCrossEncoder


class RerankProvider(Protocol):
    """Rerank 协议"""

    def rerank(self, query: str, documents: list[str]) -> list[float]:
        """对文档嵌入进行 Rerank，返回与查询嵌入的相似度分数列表

        Args:
            query (str): 查询文本
            documents (list[str]): 待 Rerank 的文档列表

        Returns:
            list[float]: 与查询嵌入的相似度分数列表，长度与 documents 相同
        """
        ...


class FastRerankAdapter:
    """基于 fastembed 的 Rerank 适配器"""

    def __init__(self, model_name: str, cache_dir: str | None = None):
        # TODO: model_name 由顶层 IoC 注入，基于传入 -> 环境变量 -> 默认值的方式确定
        self.model_name = model_name
        self.cache_dir = cache_dir

        self.reranker = TextCrossEncoder(
            model_name=self.model_name, cache_dir=self.cache_dir
        )

    def rerank(self, query: str, documents: list[str]) -> list[float]:
        """使用 fastembed 的 TextCrossEncoder 对文档嵌入进行 Rerank"""
        return list(self.reranker.rerank(query, documents))
