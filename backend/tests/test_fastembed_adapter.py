import app.rag.embedding.fast_embedding as fast_embedding_module


class _DummyTextEmbedding:
    def __init__(self, model_name=None, cache_dir=None):
        self.model_name = model_name
        self.cache_dir = cache_dir

    def embed(self, documents):
        return []

    def query_embed(self, query):
        return []


def _build_adapter(monkeypatch, model_name="test-model"):
    """统一创建 adapter，避免每个测试重复 monkeypatch 初始化逻辑。"""
    monkeypatch.setattr(fast_embedding_module, "TextEmbedding", _DummyTextEmbedding)
    return fast_embedding_module.FastEmbeddingAdapter(model_name=model_name)


def test_init_uses_settings_when_model_name_is_empty(monkeypatch):
    # 验证 model_name 为空时会回退到 settings 中的默认模型名。
    monkeypatch.setattr(
        fast_embedding_module.settings, "embedding_model_name", "bge-small-zh"
    )
    monkeypatch.setattr(fast_embedding_module.settings, "fastembed_model_path", "")
    adapter = _build_adapter(monkeypatch, model_name="")

    assert adapter.model_name == "bge-small-zh"
    assert adapter.cache_dir is None
    assert isinstance(adapter.embedding, _DummyTextEmbedding)
    assert adapter.embedding.model_name == "bge-small-zh"
    assert adapter.embedding.cache_dir is None


def test_embed_documents_returns_list_of_float_lists(monkeypatch):
    # 验证返回值被标准化为 list[list[float]]。
    adapter = _build_adapter(monkeypatch)

    class _EmbeddingStub:
        def embed(self, documents):
            return [(0.1, 0.2), (0.3, 0.4)]

    adapter.embedding = _EmbeddingStub()

    result = adapter.embed_documents(["hello", "world"])

    assert result == [[0.1, 0.2], [0.3, 0.4]]


def test_embed_documents_empty_input_returns_empty_list(monkeypatch):
    adapter = _build_adapter(monkeypatch)

    class _EmbeddingStub:
        def embed(self, documents):
            return []

    adapter.embedding = _EmbeddingStub()

    result = adapter.embed_documents([])

    assert result == []


def test_embed_query_returns_list_of_float_lists(monkeypatch):
    # 验证 query_embed 的结果也会被转换成外层 list。
    adapter = _build_adapter(monkeypatch)

    class _EmbeddingStub:
        def query_embed(self, query):
            return [(0.9, 0.8, 0.7)]

    adapter.embedding = _EmbeddingStub()

    result = adapter.embed_query("what is ai?")

    assert result == [[0.9, 0.8, 0.7]]
