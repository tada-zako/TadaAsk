from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ChatMessageRole, SearchMode, SourceType
from app.db.models import ChatMessage, DocumentChunk, Source, SourceItem
from app.db.schemas import HybridSearchOptions, HybridSearchResult
from app.rag import FTSResult, QueryExpander
from app.services.search.hybrid_search import (
    HybridSearchService,
    RankedItem,
    RankedList,
    SearchSourceRef,
)
from app.services.search.retrieval import RAGRetrievalService
from app.services.utils import TokenBudget
from tests.helpers import (
    FakeCompleter,
    FakeEmbeddingProvider,
    FakeRerankProvider,
    FakeTokenCounter,
    FakeVectorDatabase,
)


class RecordingFTS:
    def __init__(self, results: list[FTSResult]) -> None:
        self.results = results
        self.semantic_calls: list[tuple[str, list[int], int]] = []
        self.keyword_calls: list[tuple[list[str], list[int], int]] = []

    def tokenize_for_index(self, text: str) -> str:
        return text

    async def semantic_search(self, session, user_query, *, source_item_ids, limit):
        self.semantic_calls.append((user_query, list(source_item_ids), limit))
        return self.results[:limit]

    async def keywords_search(self, session, lex_queries, *, source_item_ids, limit):
        self.keyword_calls.append((list(lex_queries), list(source_item_ids), limit))
        return self.results[:limit]


class RecordingVectorDB(FakeVectorDatabase):
    def __init__(self) -> None:
        super().__init__()
        self.where_filters: list[dict | None] = []

    def query_collection(self, *args, where=None, **kwargs):
        self.where_filters.append(where)
        return super().query_collection(*args, where=where, **kwargs)


class FailingVectorDB(FakeVectorDatabase):
    def query_collection(self, *args, **kwargs):
        raise RuntimeError("vector backend unavailable")


async def create_search_data(session: AsyncSession) -> tuple[SearchSourceRef, list[DocumentChunk]]:
    source = Source(
        source_name=f"search-{id(session)}",
        collection_name=f"search-{id(session)}",
        source_type=SourceType.LOCAL_FILE,
    )
    session.add(source)
    await session.flush()

    item = SourceItem(
        source_id=source.id,
        item_key="document.txt",
        title="Document title",
        filename="document.txt",
        storage_key="documents/document.txt",
        item_hash="hash",
    )
    session.add(item)
    await session.flush()

    rows = [
        DocumentChunk(
            source_item_id=item.id,
            vector_id="vector-1",
            chunk_index=0,
            chunk_hash="hash-1",
            chunk_content="python deployment guide",
            chunk_tokens="python deployment guide",
            chunk_pos=0,
            section_header="Install",
            page_number=2,
            metadata_json={"anchor": "#install"},
        ),
        DocumentChunk(
            source_item_id=item.id,
            vector_id="vector-2",
            chunk_index=1,
            chunk_hash="hash-2",
            chunk_content="unrelated appendix",
            chunk_tokens="unrelated appendix",
            chunk_pos=30,
        ),
    ]
    session.add_all(rows)
    await session.flush()
    return (
        SearchSourceRef(
            id=source.id,
            uid=source.uid,
            collection_name=source.collection_name,
            source_item_ids=[item.id],
        ),
        rows,
    )


def build_search_service(session_factory, vector_db, fts, rerank) -> HybridSearchService:
    return HybridSearchService(
        session_factory=session_factory,
        vector_db=vector_db,
        query_expander=QueryExpander(cache_enabled=False),
        embedding=FakeEmbeddingProvider(),
        fts_provider=fts,
        rerank_provider=rerank,
    )


def test_rrf_merge_honors_weights_ignores_invalid_chunks_and_limits() -> None:
    service = build_search_service(None, FakeVectorDatabase(), RecordingFTS([]), FakeRerankProvider())

    merged = service._rrf_merge(
        [
            RankedList("fts", [RankedItem(1), RankedItem(-1)], weight=1.0),
            RankedList("vector", [RankedItem(2), RankedItem(1)], weight=2.0),
        ],
        k=1,
        limit=1,
    )

    assert merged == [(1, pytest.approx(1 / 2 + 2 / 3))]


@pytest.mark.asyncio
async def test_fast_hybrid_search_merges_fts_and_vector_and_filters_source_items(
    db_session: AsyncSession,
    session_factory,
) -> None:
    source_ref, chunks = await create_search_data(db_session)
    await db_session.commit()
    vector_db = RecordingVectorDB()
    vector_db.create_collection(source_ref.collection_name)
    embedding = FakeEmbeddingProvider()
    vector_db.add_data_to_collection(
        source_ref.collection_name,
        ["vector-1", "unmapped-vector"],
        [embedding.embed_query("one"), embedding.embed_query("two")],
        [
            {"source_item_id": source_ref.source_item_ids[0], "chunk_index": 0},
            {"source_item_id": 999, "chunk_index": 0},
        ],
    )
    fts = RecordingFTS([FTSResult(chunk_id=chunks[0].id, score=0.1)])
    rerank = FakeRerankProvider()
    service = build_search_service(session_factory, vector_db, fts, rerank)

    results = await service.search(
        query="python deployment",
        sources=[source_ref],
        options=HybridSearchOptions(mode=SearchMode.FAST, top_k=1),
        completer=FakeCompleter(),
    )

    assert [result.chunk_id for result in results] == [chunks[0].id]
    assert fts.semantic_calls == [("python deployment", source_ref.source_item_ids, 30)]
    assert vector_db.where_filters == [{"source_item_id": {"$in": source_ref.source_item_ids}}]
    assert rerank.calls == [("python deployment", ["python deployment guide"])]


@pytest.mark.asyncio
async def test_search_handles_empty_sources_component_failure_and_adaptive_fallback(
    session_factory,
) -> None:
    fts = RecordingFTS([])
    service = build_search_service(session_factory, FakeVectorDatabase(), fts, FakeRerankProvider())

    assert await service.search(
        query="empty",
        sources=[],
        options=HybridSearchOptions(mode=SearchMode.FAST),
        completer=FakeCompleter(),
    ) == []

    source = SearchSourceRef(1, "source", "missing", [1])
    service._full_hybrid_search = AsyncMock(return_value=[])
    await service.search(
        query="needs expansion",
        sources=[source],
        options=HybridSearchOptions(
            mode=SearchMode.ADAPTIVE,
            min_candidates=1,
            min_common_overlap=1,
        ),
        completer=FakeCompleter(),
    )
    service._full_hybrid_search.assert_awaited_once()


@pytest.mark.asyncio
async def test_full_search_uses_keyword_fts_and_can_skip_reranking(
    db_session: AsyncSession,
    session_factory,
) -> None:
    source_ref, chunks = await create_search_data(db_session)
    await db_session.commit()
    vector_db = RecordingVectorDB()
    vector_db.create_collection(source_ref.collection_name)
    embedding = FakeEmbeddingProvider()
    vector_db.add_data_to_collection(
        source_ref.collection_name,
        ["vector-1"],
        [embedding.embed_query("document")],
        [{"source_item_id": source_ref.source_item_ids[0], "chunk_index": 0}],
    )
    fts = RecordingFTS([FTSResult(chunk_id=chunks[0].id, score=0.1)])
    rerank = FakeRerankProvider()
    service = build_search_service(session_factory, vector_db, fts, rerank)

    results = await service.search(
        query="how to deploy",
        sources=[source_ref],
        options=HybridSearchOptions(
            mode=SearchMode.FULL,
            top_k=1,
            rerank_enabled=False,
            max_keywords=1,
            max_alternative_queries=1,
        ),
        completer=FakeCompleter(
            structured_result={
                "keywords": ["deploy"],
                "alternative_queries": ["deployment guide"],
                "hypothetical_document": "A deployment guide",
            }
        ),
    )

    assert [result.chunk_id for result in results] == [chunks[0].id]
    assert fts.keyword_calls == [(["deploy"], source_ref.source_item_ids, 30)]
    assert rerank.calls == []
    assert results[0].rerank_score is None


@pytest.mark.asyncio
async def test_search_returns_fts_hits_when_vector_component_fails(
    db_session: AsyncSession,
    session_factory,
) -> None:
    source_ref, chunks = await create_search_data(db_session)
    await db_session.commit()
    service = build_search_service(
        session_factory,
        FailingVectorDB(),
        RecordingFTS([FTSResult(chunk_id=chunks[0].id, score=0.1)]),
        FakeRerankProvider(),
    )

    results = await service.search(
        query="deployment",
        sources=[source_ref],
        options=HybridSearchOptions(mode=SearchMode.FAST, top_k=1),
        completer=FakeCompleter(),
    )

    assert [result.chunk_id for result in results] == [chunks[0].id]


@pytest.mark.asyncio
async def test_rag_retrieval_builds_citations_snapshot_and_standalone_query() -> None:
    result = HybridSearchResult(
        chunk_id=7,
        vector_id="vector-7",
        chunk_index=0,
        content=" excerpt ",
        source_id=3,
        source_uid="source-uid",
        source_name="Source",
        source_item_id=4,
        source_item_uid="item-uid",
        title="Guide",
        filename="guide.md",
        origin_url="https://example.test/guide",
        section_header="Setup",
        page_number=5,
        metadata={"anchor": "#setup"},
    )
    hybrid = AsyncMock()
    hybrid.search = AsyncMock(return_value=[result, result])
    retrieval = RAGRetrievalService(hybrid_search_service=hybrid, token_counter=FakeTokenCounter())
    completer = FakeCompleter(structured_result={"query": "rewritten question"})
    recent = [ChatMessage(sequence=1, role=ChatMessageRole.USER, message="older", provider="p", model="m", chat_session_id=1)]

    retrieved = await retrieval.retrieve_for_chat(
        sources=[],
        user_query="follow up",
        recent_messages=recent,
        compaction_message=None,
        rag_options=HybridSearchOptions(standalone_enabled=True),
        completer=completer,
        token_budget=TokenBudget(context_window_tokens=50, max_output_tokens=10),
    )

    assert hybrid.search.await_args.kwargs["query"] == "rewritten question"
    assert [item.citation_id for item in retrieved.snapshot.items] == [1, 2]
    assert retrieved.snapshot.items[0].anchor == "#setup"
    assert retrieved.snapshot.items[0].excerpt == "excerpt"
    assert "[[citation:1]] Guide / Setup" in retrieved.context_content


@pytest.mark.asyncio
async def test_rag_retrieval_empty_result_has_valid_empty_snapshot() -> None:
    hybrid = AsyncMock()
    hybrid.search = AsyncMock(return_value=[])
    retrieval = RAGRetrievalService(hybrid_search_service=hybrid, token_counter=FakeTokenCounter())

    retrieved = await retrieval.retrieve_for_chat(
        sources=[],
        user_query="unknown",
        recent_messages=[],
        compaction_message=None,
        rag_options=HybridSearchOptions(),
        completer=FakeCompleter(),
        token_budget=TokenBudget(context_window_tokens=20, max_output_tokens=5),
    )

    assert retrieved.context_content is None
    assert retrieved.snapshot.query == "unknown"
    assert retrieved.snapshot.items == []
