from fastembed import TextEmbedding

from app.core.config import settings


class FastEmbeddingAdapter:
    """基于 fastembed 的文本嵌入适配器"""

    def __init__(self, model_name: str = settings.embedding_model_name):
        self.model_name = model_name or settings.embedding_model_name
        self.cache_dir = settings.fastembed_model_path or None

        self.embedding = TextEmbedding(
            model_name=self.model_name, cache_dir=self.cache_dir
        )

    def embed_documents(self, documents: list[str]) -> list[list[float]]:
        """将文档列表转换为嵌入向量列表"""
        return [list(e) for e in self.embedding.embed(documents)]

    def embed_query(self, query: str) -> list[list[float]]:
        """将查询文本转换为嵌入向量"""
        return [list(e) for e in self.embedding.query_embed(query)]
