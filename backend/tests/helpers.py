from __future__ import annotations

import hashlib
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, TypeVar

import numpy as np
from pydantic import BaseModel

from app.providers import (
    Message,
    ModelResponse,
    ModelSettings,
    StreamedResponse,
    TokenUsage,
)
from app.rag import TextChunk, VectorQueryResult


class FakeEmbeddingProvider:
    """确定性的轻量 embedding，避免测试下载真实模型。"""

    def __init__(self, dimension: int = 8) -> None:
        self.dimension = dimension
        self.document_calls: list[list[str]] = []
        self.query_calls: list[str] = []

    def _embed(self, text: str) -> np.ndarray:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values = [digest[index] / 255 for index in range(self.dimension)]
        return np.asarray(values, dtype=np.float32)

    def embed_documents(self, documents: list[str]) -> list[np.ndarray]:
        self.document_calls.append(list(documents))
        return [self._embed(document) for document in documents]

    def embed_query(self, query: str) -> np.ndarray:
        self.query_calls.append(query)
        return self._embed(query)


class FakeRerankProvider:
    """按查询词重叠比例返回稳定分数。"""

    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str]]] = []

    def rerank(self, query: str, documents: list[str]) -> list[float]:
        self.calls.append((query, list(documents)))
        query_terms = set(query.lower().split())
        if not query_terms:
            return [0.0 for _ in documents]
        return [
            len(query_terms & set(document.lower().split())) / len(query_terms)
            for document in documents
        ]


class FakeVectorDatabase:
    """内存向量库；实现业务层当前使用的 VectorDatabase 协议。"""

    def __init__(self) -> None:
        self.collections: dict[
            str,
            dict[str, tuple[np.ndarray, dict[str, Any]]],
        ] = {}

    def create_collection(self, collection_name: str) -> None:
        self.collections.setdefault(collection_name, {})

    def add_data_to_collection(
        self,
        collection_name: str,
        ids: list[str],
        embeddings: list[np.ndarray],
        metadatas: list[dict[str, Any]],
    ) -> None:
        collection = self.collections.setdefault(collection_name, {})
        for vector_id, embedding, metadata in zip(ids, embeddings, metadatas):
            collection[vector_id] = (
                np.asarray(embedding, dtype=np.float32),
                dict(metadata),
            )

    def update_data_in_collection(
        self,
        collection_name: str,
        ids: list[str],
        embeddings: list[np.ndarray],
        metadatas: list[dict[str, Any]],
    ) -> None:
        self.add_data_to_collection(
            collection_name,
            ids,
            embeddings,
            metadatas,
        )

    def delete_data_from_collection(
        self,
        collection_name: str,
        ids: list[str],
    ) -> None:
        collection = self.collections.get(collection_name, {})
        for vector_id in ids:
            collection.pop(vector_id, None)

    def query_collection(
        self,
        collection_name: str,
        query_embedding: np.ndarray,
        top_k: int = 5,
        where: dict[str, Any] | None = None,
    ) -> list[VectorQueryResult]:
        allowed_item_ids: set[int] | None = None
        if where:
            source_item_filter = where.get("source_item_id", {})
            if "$in" in source_item_filter:
                allowed_item_ids = set(source_item_filter["$in"])

        matches: list[VectorQueryResult] = []
        for vector_id, (embedding, metadata) in self.collections.get(
            collection_name, {}
        ).items():
            if (
                allowed_item_ids is not None
                and metadata.get("source_item_id") not in allowed_item_ids
            ):
                continue
            distance = float(
                np.linalg.norm(
                    np.asarray(query_embedding, dtype=np.float32) - embedding
                )
            )
            matches.append(
                VectorQueryResult(
                    vector_id=vector_id,
                    metadata=dict(metadata),
                    distance=distance,
                )
            )
        return sorted(matches, key=lambda item: item.distance)[:top_k]

    def delete_collection(self, collection_name: str) -> None:
        self.collections.pop(collection_name, None)


class FakeTextSplitter:
    """按字符数切分文本，适合索引编排测试。"""

    def __init__(self, chunk_size: int = 200) -> None:
        self.chunk_size = chunk_size

    async def split_text(self, text: str, file_path: str) -> list[TextChunk]:
        del file_path
        return [
            TextChunk(content=text[pos : pos + self.chunk_size], pos=pos)
            for pos in range(0, len(text), self.chunk_size)
            if text[pos : pos + self.chunk_size]
        ]


class FakeTokenCounter:
    """使用字符近似 token，便于精确构造预算边界。"""

    def count_message(self, text: str) -> int:
        return len(text)

    def truncate_text(self, text: str, max_tokens: int) -> str:
        return text[: max(0, max_tokens)]


class FakeStreamedResponse(StreamedResponse):
    def __init__(
        self,
        chunks: list[str],
        *,
        usage: TokenUsage | None = None,
        error: Exception | None = None,
    ) -> None:
        super().__init__()
        self._chunks = chunks
        self._usage = usage or TokenUsage()
        self._error = error
        self.closed = False

    async def _get_stream_iter(self) -> AsyncIterator[str]:
        for chunk in self._chunks:
            if self._cancelled:
                break
            self._text_buffer.append(chunk)
            yield chunk
        if self._error:
            raise self._error

    async def close_stream(self) -> None:
        self.closed = True


SchemaT = TypeVar("SchemaT", bound=BaseModel)


class FakeCompleter:
    """同时实现文本流式生成和结构化输出协议。"""

    def __init__(
        self,
        *,
        chunks: list[str] | None = None,
        usage: TokenUsage | None = None,
        structured_result: BaseModel | dict[str, Any] | None = None,
        error: Exception | None = None,
        provider_name: str = "fake",
        model_name: str = "fake-model",
    ) -> None:
        self.chunks = chunks or ["ok"]
        self.usage = usage or TokenUsage()
        self.structured_result = structured_result
        self.error = error
        self._provider_name = provider_name
        self._model_name = model_name
        self.chat_calls: list[tuple[list[Message], ModelSettings]] = []
        self.stream_calls: list[tuple[list[Message], ModelSettings]] = []
        self.structured_calls: list[tuple[list[Message], ModelSettings, type]] = []
        self.last_stream: FakeStreamedResponse | None = None

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def provider_name(self) -> str:
        return self._provider_name

    async def chat(
        self,
        *,
        messages: list[Message],
        model_settings: ModelSettings,
    ) -> ModelResponse:
        self.chat_calls.append((list(messages), model_settings))
        if self.error:
            raise self.error
        return ModelResponse(
            text="".join(self.chunks),
            usage=self.usage,
        )

    @asynccontextmanager
    async def stream_chat(
        self,
        *,
        messages: list[Message],
        model_settings: ModelSettings,
    ) -> AsyncIterator[FakeStreamedResponse]:
        self.stream_calls.append((list(messages), model_settings))
        stream = FakeStreamedResponse(
            list(self.chunks),
            usage=self.usage,
            error=self.error,
        )
        self.last_stream = stream
        try:
            yield stream
        finally:
            await stream.close_stream()

    async def complete_structured(
        self,
        *,
        messages: list[Message],
        model_settings: ModelSettings,
        schema: type[SchemaT],
    ) -> SchemaT:
        self.structured_calls.append((list(messages), model_settings, schema))
        if self.error:
            raise self.error
        if self.structured_result is None:
            raise AssertionError("FakeCompleter.structured_result is not configured")
        return schema.model_validate(self.structured_result)
