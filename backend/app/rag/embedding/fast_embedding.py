from fastembed import TextEmbedding

from app.core.config import settings


class FastEmbeddingAdapter:
    """基于 fastembed 的文本嵌入适配器"""

    def __init__(self, model_name: str):
        self.cache_dir = settings.fastembed_model_path or None

        # 将 HF 格式的 model_name 映射为 fastembed 内部名称，找不到则原样传入
        hf_to_fastembed = {
            info["sources"]["hf"]: info["model"]
            for info in TextEmbedding.list_supported_models()
            if info["sources"].get("hf")
        }
        self.model_name = hf_to_fastembed.get(model_name, model_name)

        self.embedding = TextEmbedding(
            model_name=self.model_name, cache_dir=self.cache_dir
        )

    def embed_documents(self, documents: list[str]) -> list[list[float]]:
        """将文档列表转换为嵌入向量列表"""
        return [list(e) for e in self.embedding.embed(documents)]

    def embed_query(self, query: str) -> list[list[float]]:
        """将查询文本转换为嵌入向量"""
        return [list(e) for e in self.embedding.query_embed(query)]
