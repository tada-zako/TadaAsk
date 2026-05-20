from typing import Protocol


class EmbeddingProvider(Protocol):
    """文档嵌入协议"""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """将文本列表转换为嵌入向量列表

        Args:
            texts (list[str]): 待转换的文本列表

        Returns:
            list[list[float]]: 转换后的嵌入向量列表
        """
        ...

    def embed_query(self, text: str) -> list[float]:
        """将查询文本转换为嵌入向量

        Args:
            text (str): 待转换的查询文本

        Returns:
            list[float]: 转换后的查询嵌入向量
        """
        ...
