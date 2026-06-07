import asyncio
from typing import AsyncIterable, cast, Any
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, Field, ConfigDict
from pydantic.alias_generators import to_camel
from loguru import logger

from app.rag import (
    VectorDatabase,
    VectorQueryResult,
    QueryExpander,
    ExpandedQuery,
    FTSProvider,
    FTSResult,
    EmbeddingProvider,
    RerankProvider,
)
from app.db.models import Source, SourceItem
from app.db.schemas import DocumentChunkInternal
from app.crud import SourceCRUD, RAGSearchCRUD
from app.core.constants import SearchMode
from app.utils import TTLCache


@dataclass
class HybridSearchOptions:
    mode: SearchMode = SearchMode.ADAPTIVE  # 搜索模式
    top_k: int = 10

    # 召回候选数量
    fts_k: int = 30
    vector_k: int = 20
    rrf_k: int = 60  # RRF 算法中的参数 K
    rerank_k: int = 12

    # expansion 策略
    # expansion_enabled: bool = True
    max_alternative_queries: int = 2

    # rerank 策略
    rerank_enabled: bool = False

    # 并发限制
    vector_search_concurrency: int = 6

    # adaptive 判断；判断是否需要进入 FULL 模式
    min_candidates_before_expansion: int = 8
    min_overlap_before_expansion: int = 1


@dataclass
class HybridSearchResult:
    """混合搜索结果数据结构"""

    chunk_id: int
    vector_id: str
    chunk_index: int
    content: str

    source_id: int
    source_uid: str
    source_name: str

    source_item_id: int
    source_item_uid: str
    title: str
    filename: str
    origin_url: str | None = None

    page_number: int | None = None
    section_header: str | None = None
    metadata: dict[str, Any] | None = None

    rrf_score: float | None = None
    rerank_score: float | None = None


@dataclass
class RankedItem:
    """RRF rank 传递内部 item 数据结构"""

    chunk_id: int
    score: float | None = None


@dataclass
class RankedList:
    """RRF rank 传递列表数据结构"""

    name: str
    items: list[RankedItem]
    weight: float = 1.0


class SearchDebugInfo(BaseModel):
    """搜索调试信息结构体"""

    expanded_queries: list[ExpandedQuery] | None = None
    candidate_counts: dict[str, int] = Field(default_factory=dict)
    latency_ms: dict[str, float] = Field(default_factory=dict)
    confidence: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )


class HybridSearchResponse(BaseModel):
    """混合搜索响应结构体"""

    raw_query: str
    results: list[HybridSearchResult] = Field(default_factory=list)
    debug_info: SearchDebugInfo | None = None


class HybridSearchService:
    def __init__(
        self,
        *,
        session: AsyncSession,
        source_crud: SourceCRUD,
        rag_search_crud: RAGSearchCRUD,
        vector_db: VectorDatabase,
        query_expander: QueryExpander,
        embedding: EmbeddingProvider,
        fts_provider: FTSProvider,
        rerank_provider: RerankProvider,
    ):
        """具体的参数由依赖注入"""
        self.session = session
        self.source_crud = source_crud
        self.rag_search_crud = rag_search_crud
        self.vector_db = vector_db
        self.query_expander = query_expander
        self.embedding = embedding
        self.fts_provider = fts_provider
        self.rerank_provider = rerank_provider

        # TODO: 缓存机制应该配置在底层 module 中，作为有状态服务的一部分
        # 简易缓存机制：对 embedding, query_expander 结果进行缓存
        # self._embedding_cache = TTLCache[str, NDArray](
        #     max_size=512,
        #     ttl_seconds=1800,
        # )
        # self._query_expansion_cache = TTLCache[str, ExpandedQuery](
        #     max_size=512,
        #     ttl_seconds=1800,
        # )

    def _rrf_merge(
        self,
        ranked_lists: list[RankedList],
        k: int = 60,
        limit: int | None = None,
    ) -> list[tuple[int, float]]:
        """
        多路 RRF 合并算法
        """
        chunk_scores: dict[int, float] = {}

        for ranked_list in ranked_lists:
            for rank, item in enumerate(ranked_list.items):
                chunk_scores[item.chunk_id] = chunk_scores.get(item.chunk_id, 0.0) + (
                    ranked_list.weight / (k + rank + 1)
                )

        # RRF 排序
        sorted_chunks = sorted(
            chunk_scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        return sorted_chunks[:limit] if limit else sorted_chunks

    async def _raw_hybrid_search(
        self,
        *,
        query: str,
        sources: list[Source],
        options: HybridSearchOptions,
        debug: SearchDebugInfo | None = None,
    ) -> tuple[list[HybridSearchResult], dict[str, Any]]:
        """
        RAW Search 阶段

        pipeline:
            1. raw embedding
            2. raw vector search + raw FTS search (并行)
            3. RRF rank
            4. rerank（可选）
            5. confidence 计算
        """

        # 1.1 创建并行任务：raw embedding
        embedding_task = asyncio.create_task(
            asyncio.to_thread(self.embedding.embed_query, query)
        )

        # 1.2 创建并行任务：raw FTS search
        source_item_ids = [
            item.id for source in sources for item in source.source_items
        ]
        fts_task = asyncio.create_task(
            self.fts_provider.semantic_search(
                session=self.session,
                user_query=query,
                source_item_ids=source_item_ids,
                limit=options.fts_k,
            )
        )

        # 1.3 等待 embedding 结果，创建 raw vector search 任务
        embedding_result = await embedding_task

        vector_search_task = asyncio.create_task(
            self._vector_search_sources(
                sources=sources,
                query_embedding=embedding_result,
                top_k=options.vector_k,
                concurrency=options.vector_search_concurrency,
                debug=debug,
            )
        )

        # 2. 等待搜索结果
        fts_results = await fts_task
        vector_results = await vector_search_task

        # 3. 执行 RRF rank
        ranked_lists, rrf_fetched_results = await self._rrf_fetch(
            fts_results=fts_results,
            vector_results=vector_results,
            sources=sources,
            rrf_k=options.rrf_k,
            limit=options.rerank_k,  # RRF limit 使用 rerank_k，避免后续 rerank 计算过多
            debug=debug,
        )

        # 4. 可选的 rerank
        if options.rerank_enabled:
            ranked_results = await self._rerank(
                rrf_fetched_results=rrf_fetched_results,
                query=query,
                debug=debug,
            )
        else:
            ranked_results = rrf_fetched_results[: options.rerank_k]

        # 5. 计算 confidence
        confidence = self._estimate_confidence(
            fts_results=fts_results,
            vector_results=vector_results,
            ranked_results=ranked_results,
            debug=debug,
        )

        if debug:
            debug.candidate_counts.update(
                {
                    "fts": len(fts_results),
                    "vector": len(vector_results),
                    "rrf_candidates": sum(len(lst.items) for lst in ranked_lists),
                }
            )

        return ranked_results, confidence

    async def _vector_search_sources(
        self,
        *,
        sources: list[Source],
        query_embedding: NDArray[np.float32],
        top_k: int,
        concurrency: int = 6,
        debug: SearchDebugInfo | None = None,
    ) -> list[VectorQueryResult]:
        """
        多向量 collection 查询
        """

        # TODO: 这里的并发控制应该提升到更通用的层面，作为有状态服务的一部分；目前先在这里实现一个简单的 Semaphore 控制并发量
        semaphore = asyncio.Semaphore(concurrency)

        async def query_one_source(source: Source) -> list[VectorQueryResult]:
            async with semaphore:
                return await asyncio.to_thread(
                    self.vector_db.query_collection,
                    collection_name=source.collection_name,
                    query_embedding=query_embedding,
                    top_k=top_k,
                    where={
                        "source_item_id": {
                            # NOTE: 确保不会检索到 ingest 未 completed 的相关数据
                            "$in": [item.id for item in source.source_items]
                        }
                    },
                )

        results = await asyncio.gather(
            *[query_one_source(source) for source in sources],
            return_exceptions=True,
        )
        # 扁平化结果列表
        return [
            item for sublist in results if isinstance(sublist, list) for item in sublist
        ]

    async def _rrf_fetch(
        self,
        *,
        fts_results: list[FTSResult],
        vector_results: list[VectorQueryResult],
        sources: list[Source],
        rrf_k: int,
        limit: int,
        debug: SearchDebugInfo | None = None,
    ) -> list[HybridSearchResult]:
        """
        进行 RRF rank 后的结果
        """

        # 0. 构建 vector_id -> chunk_id 的映射
        vector_id_to_chunk_id = await self.rag_search_crud.get_chunk_ids_by_vector_ids(
            vector_ids=[r.vector_id for r in vector_results],
        )

        # 1. 构建 RRF 输入的 ranked lists
        fts_ranked_list = RankedList(
            name="fts_raw",
            items=[
                RankedItem(
                    chunk_id=r.chunk_id,
                    score=r.score,
                )
                for r in fts_results
            ],
            weight=2.0,
        )

        vector_ranked_list = RankedList(
            name="vector_raw",
            items=[
                RankedItem(
                    chunk_id=vector_id_to_chunk_id.get(
                        r.vector_id, -1
                    ),  # 如果没有找到对应的 chunk_id，则使用 -1 占位，后续会被过滤掉
                    score=r.distance,
                )
                for r in vector_results
            ],
            weight=2.0,
        )

        ranked_lists = [fts_ranked_list, vector_ranked_list]

        # 2. 执行 RRF 合并
        rrf_results = self._rrf_merge(ranked_lists, k=rrf_k, limit=limit)

        # 3. 从数据库获取 hybrid search 结果
        if not rrf_results:
            return []

        chunk_ids = [chunk_id for chunk_id, _ in rrf_results]
        chunk_id_to_rrf_score = dict(rrf_results)

        fetched_results: list[
            HybridSearchResult
        ] = await self.rag_search_crud.get_search_results_by_chunk_ids(
            chunk_ids=chunk_ids
        )

        for result in fetched_results:
            result.rrf_score = chunk_id_to_rrf_score.get(result.chunk_id)
        return fetched_results

    async def search(
        self,
        *,
        query: str,
        sources: list[Source],
        options: HybridSearchOptions,
        enable_debug: bool = False,
    ) -> list[HybridSearchResult]:
        """
        Hybrid Search 主方法
        """

        debug = SearchDebugInfo() if enable_debug else None

        # ======= 1. RAW search 阶段 =======
        raw_search_results, raw_confidence = await self._raw_hybrid_search(
            query=query,
            sources=sources,
            options=options,
            debug=debug,
        )

        # ======= 2. 基于 option.mode 进行分支判断 =======
        if options.mode == SearchMode.FAST:
            # 快速模式：直接返回
            return raw_search_results

        if options.mode == SearchMode.ADAPTIVE and self._is_confident_enough(
            raw_confidence, options, debug
        ):
            # 自适应模式：如果 raw search 结果足够好，则直接返回
            return raw_search_results

        # ======= 3. FULL search 阶段 =======
        full_search_results = await self._full_hybrid_search(
            query=query,
            sources=sources,
            options=options,
            raw_search_results=raw_search_results,  # 复用 raw search 的处理结果
            debug=debug,
        )

        return full_search_results
