from fastembed import TextEmbedding


def map_hf_to_fastembed(model_name: str) -> str:
    """
    将 HuggingFace 模型名称映射为 fastembed 内部名称
    TODO: 该函数放置到顶层创建 EmbeddingProvider 时调用，方便 rerank 部分复用
    """
    # 将 HF 格式的 model_name 映射为 fastembed 内部名称，找不到则原样传入
    hf_to_fastembed = {
        info["sources"]["hf"]: info["model"]
        for info in TextEmbedding.list_supported_models()
        if info["sources"].get("hf")
    }
    return hf_to_fastembed.get(model_name, model_name)


class FastEmbeddingAdapter:
    """基于 fastembed 的文本嵌入适配器"""

    def __init__(self, model_name: str, cache_dir: str | None = None):
        self.model_name = model_name
        self.cache_dir = cache_dir

        self.embedding = TextEmbedding(
            model_name=self.model_name, cache_dir=self.cache_dir
        )

    def embed_documents(self, documents: list[str]) -> list[list[float]]:
        """将文档列表转换为嵌入向量列表"""
        return [list(e) for e in self.embedding.embed(documents)]

    def embed_query(self, query: str) -> list[list[float]]:
        """将查询文本转换为嵌入向量"""
        return [list(e) for e in self.embedding.query_embed(query)]
