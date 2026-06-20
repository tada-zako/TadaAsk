import asyncio
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession
import numpy as np
from numpy.typing import NDArray
from loguru import logger

from ..schemas import RawSearchConfidence, SearchDebugInfo
from ..utils import track_latency
from app.rag import (
    VectorDatabase,
    VectorQueryResult,
    QueryExpander,
    FTSProvider,
    EmbeddingProvider,
    RerankProvider,
)
from app.providers import StructuredCompleter
from app.db.models import Source
from app.db.schemas import HybridSearchResult, HybridSearchOptions
from app.crud import SourceCRUD, RAGSearchCRUD
from app.core.constants import SearchMode


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
                # 过滤无效 chunk_id
                if item.chunk_id == -1:
                    continue

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

    async def _vector_search_sources(
        self,
        *,
        sources: list[Source],
        query_embedding: NDArray[np.float32],
        top_k: int,
        concurrency: int = 6,
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

    async def _rrf_fetch_and_rerank(
        self,
        *,
        query: str,
        ranked_lists: list[RankedList],
        options: HybridSearchOptions,
    ) -> list[HybridSearchResult]:
        """
        RRF fetch + rerank 阶段
        rerank 可选
        """

        # 1. 执行 RRF 合并
        rrf_results = self._rrf_merge(
            ranked_lists,
            k=options.rrf_k,
            # 使用 rerank_k 作为 RRF 候选数量；减少 rerank 计算量
            limit=options.rerank_k,
        )
        if not rrf_results:
            return []

        # 2. 提取 chunk_id 列表，构建 chunk_id -> rrf_score 映射
        chunk_ids = [chunk_id for chunk_id, _ in rrf_results]
        chunk_id_to_rrf_score = dict(rrf_results)

        # 3. 基于 chunk_id 获取对应的 search result 详情
        ranked_hits = await self.rag_search_crud.get_ranked_results_by_chunk_ids(
            chunk_ids=chunk_ids
        )

        # 3.1 如果没有命中结果，直接返回
        if not ranked_hits:
            return []

        documents = [result.content for result in ranked_hits]

        if options.rerank_enabled:
            # 4. 执行 rerank 操作
            rerank_scores = await asyncio.to_thread(
                self.rerank_provider.rerank,
                query=query,
                documents=documents,
            )
        else:
            rerank_scores = [None] * len(ranked_hits)

        # 5. 附加 RRF score 和 rerank score 到结果中
        for hit, rerank_score in zip(ranked_hits, rerank_scores):
            hit.rrf_score = chunk_id_to_rrf_score.get(hit.chunk_id)
            hit.rerank_score = rerank_score

        # 6. 基于 rerank_score 进行最终排序
        sorted_reranked = sorted(
            ranked_hits,
            key=lambda x: x.rerank_score
            if x.rerank_score is not None
            else float("-inf"),
            reverse=True,
        )

        return sorted_reranked[: options.rerank_k]

    def _estimate_confidence(
        self,
        *,
        fts_results: list[RankedItem],
        vector_results: list[RankedItem],
        raw_hits: list[HybridSearchResult],
        debug: SearchDebugInfo | None = None,
    ) -> RawSearchConfidence:
        """
        统计 raw search 结果的 confidence；
        """

        # 计算 FTS, vector, rerank 结果重叠程度
        fts_chunk_ids = {r.chunk_id for r in fts_results}
        # 过滤无效 chunk_id
        vector_chunk_ids = {r.chunk_id for r in vector_results if r.chunk_id != -1}
        hit_chunk_ids = {hit.chunk_id for hit in raw_hits}

        common_overlap_count = len(fts_chunk_ids & vector_chunk_ids)
        rerank_overlap_count = len(hit_chunk_ids & fts_chunk_ids & vector_chunk_ids)

        # 计算 raw_search score gap
        raw_top_score = raw_hits[0].rerank_score if raw_hits else None
        raw_second_score = raw_hits[1].rerank_score if len(raw_hits) > 1 else None
        raw_score_gap = None
        if raw_top_score is not None and raw_second_score is not None:
            raw_score_gap = raw_top_score - raw_second_score

        confidence = RawSearchConfidence(
            hit_count=len(hit_chunk_ids),
            fts_count=len(fts_chunk_ids),
            vector_count=len(vector_chunk_ids),
            common_overlap_count=common_overlap_count,
            rerank_overlap_count=rerank_overlap_count,
            hit_top_score=raw_hits[0].rrf_score if raw_hits else None,
            hit_gap=raw_score_gap,
        )

        if debug:
            debug.confidence = confidence

        return confidence

    def _is_confident_enough(
        self,
        confidence: RawSearchConfidence,
        options: HybridSearchOptions,
    ) -> bool:
        """
        判断 raw search 结果的置信度情况

        判断策略：
            - 总命中数量
            - FTS, vector, RRF+rerank 的结果重叠程度
            - FTS, vector 是否都有命中结果 (暂不启用)
            - 命中结果的 rerank score gap 是否不超过阈值 (暂不启用)
        """

        # 总命中
        if confidence.hit_count < options.min_candidates:
            return False

        # FTS, vector 命中数量
        # if confidence.fts_count == 0 or confidence.vector_count == 0:
        #     return False

        # 重叠程度
        if confidence.common_overlap_count < options.min_common_overlap:
            return False
        if confidence.rerank_overlap_count < options.min_rerank_overlap:
            return False

        # 命中结果的 rerank score gap
        # if (
        #     confidence.hit_top_score is not None
        #     and confidence.hit_gap is not None
        #     and confidence.hit_gap > options.max_hit_score_gap_threshold
        # ):
        #     return False

        return True

    async def _raw_hybrid_search(
        self,
        *,
        query: str,
        sources: list[Source],
        options: HybridSearchOptions,
        debug: SearchDebugInfo | None = None,
    ) -> tuple[list[RankedList], list[HybridSearchResult]]:
        """
        RAW Search 阶段

        pipeline:
            1. raw embedding + raw FTS search (并行)
            2. raw vector search
            3. RRF rank + rerank (可选)
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
        async with track_latency(debug, "raw_embedding"):
            embedding_result = await embedding_task

        vector_search_task = asyncio.create_task(
            self._vector_search_sources(
                sources=sources,
                query_embedding=embedding_result,
                top_k=options.vector_k,
                concurrency=options.vector_search_concurrency,
            )
        )

        # 2. 等待搜索结果
        fts_results = await fts_task
        async with track_latency(debug, "raw_vector_search"):
            vector_results = await vector_search_task

        # 3.0 构建 vector_id -> chunk_id 的映射
        vector_id_to_chunk_id = await self.rag_search_crud.get_chunk_ids_by_vector_ids(
            vector_ids=[r.vector_id for r in vector_results],
        )

        # 3.1 构建 RRF 输入的 ranked lists
        fts_ranked_list = RankedList(
            name="fts_raw",
            items=[
                RankedItem(
                    chunk_id=r.chunk_id,
                    score=r.score,
                )
                for r in fts_results
            ],
            weight=1.0,
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
            weight=1.0,
        )

        ranked_lists = [fts_ranked_list, vector_ranked_list]

        # 3.2 执行 RRF rank 以及可选的 rerank
        hit_results = await self._rrf_fetch_and_rerank(
            query=query,
            ranked_lists=ranked_lists,
            options=options,
        )

        if debug:
            debug.candidate_counts.update(
                {
                    "raw_fts": len(fts_results),
                    "raw_vector": len(vector_results),
                    "raw_final": len(hit_results),
                }
            )

        return ranked_lists, hit_results

    async def _full_hybrid_search(
        self,
        *,
        query: str,
        sources: list[Source],
        raw_ranked_lists: list[RankedList],
        options: HybridSearchOptions,
        completer: StructuredCompleter,
        debug: SearchDebugInfo | None = None,
    ) -> list[HybridSearchResult]:
        """
        FULL Search 阶段

        pipeline:
            1. query expansion
            2. expanded query embedding
            3. expanded query vector search + expanded query FTS search (并行)
            4. RRF rank + rerank (可选)；
                复用 raw_ranked_lists + expanded search ranked lists
        """

        # 1. 扩展查询
        expanded_query = await self.query_expander.expand_query(
            query=query,
            max_keywords=options.max_keywords,
            max_alternative_queries=options.max_alternative_queries,
            completer=completer,
        )

        # 2. 扩展查询 embedding
        search_texts = [
            expanded_query.hypothetical_document
        ] + expanded_query.alternative_queries

        # 2.1 创建并行任务：expanded query embedding
        embedding_tasks = [
            asyncio.create_task(asyncio.to_thread(self.embedding.embed_query, text))
            for text in search_texts
        ]

        # 3.1 创建并行任务：expanded query FTS search
        source_item_ids = [
            item.id for source in sources for item in source.source_items
        ]
        fts_task = asyncio.create_task(
            self.fts_provider.keywords_search(
                session=self.session,
                lex_queries=expanded_query.keywords,
                source_item_ids=source_item_ids,
                limit=options.fts_k,
            )
        )

        # 3.2 等待 embedding 结果，创建 expanded query vector search 任务
        async with track_latency(debug, "full_embedding"):
            embedding_results = await asyncio.gather(*embedding_tasks)

        vector_search_tasks = [
            asyncio.create_task(
                self._vector_search_sources(
                    sources=sources,
                    query_embedding=embedding_result,
                    top_k=options.vector_k,
                    concurrency=options.vector_search_concurrency,
                )
            )
            for embedding_result in embedding_results
        ]

        # 3.3 等待 search 结果
        fts_results = await fts_task
        # NOTE: 这里的 vector_results 依赖于 asyncio.gather 中任务的传入顺序，
        # 与 search_texts 顺序一致，不一定安全
        async with track_latency(debug, "full_vector_search"):
            vector_results: list[list[VectorQueryResult]] = await asyncio.gather(
                *vector_search_tasks
            )

        # 4.1 构建 FTS search 的 ranked list
        fts_ranked_list = RankedList(
            name="fts_keywords",
            items=[
                RankedItem(
                    chunk_id=r.chunk_id,
                    score=r.score,
                )
                for r in fts_results
            ],
            weight=0.9,
        )

        # 4.2 构建 vector search 的 ranked list
        vector_ranked_lists = []

        # 4.2.1 创建 vector_id -> chunk_id 的映射
        all_vector_ids = [r.vector_id for sublist in vector_results for r in sublist]
        vector_id_to_chunk_id = await self.rag_search_crud.get_chunk_ids_by_vector_ids(
            vector_ids=all_vector_ids,
        )

        for index, vector_result_list in enumerate(vector_results):
            # 4.2.2 构建 ranked list
            if index == 0:
                # hyde 查询
                weight = 0.8
                name = "vector_hyde"
            else:
                # alternative 查询
                weight = 0.7
                name = "vector_alternative"

            vector_ranked_lists.append(
                RankedList(
                    name=name,
                    items=[
                        RankedItem(
                            chunk_id=vector_id_to_chunk_id.get(
                                r.vector_id, -1
                            ),  # 如果没有找到对应的 chunk_id，则使用 -1 占位，后续会被过滤掉
                            score=r.distance,
                        )
                        for r in vector_result_list
                    ],
                    weight=weight,
                )
            )

        # 4.3 构建完整的 ranked lists；包含 raw search 和 expanded search 的结果
        all_ranked_lists = raw_ranked_lists + [fts_ranked_list] + vector_ranked_lists

        # 4.4 执行 RRF rank 以及可选的 rerank
        hit_results = await self._rrf_fetch_and_rerank(
            query=query,
            ranked_lists=all_ranked_lists,
            options=options,
        )

        if debug:
            debug.expanded_queries = expanded_query
            debug.candidate_counts.update(
                {
                    "full_fts": len(fts_results),
                    "full_vector": sum(len(lst) for lst in vector_results),
                    "full_final": len(hit_results),
                }
            )

        return hit_results

    async def search(
        self,
        *,
        query: str,
        # TODO: 之后将这里的 sources 重命名为 source_with_items
        sources: list[Source],
        options: HybridSearchOptions,
        completer: StructuredCompleter,
        enable_debug: bool = False,
    ) -> list[HybridSearchResult]:
        """
        Hybrid Search 主方法
        """

        debug = SearchDebugInfo() if enable_debug else None

        # ======= 1. RAW search 阶段 =======
        ranked_lists, raw_hits = await self._raw_hybrid_search(
            query=query,
            sources=sources,
            options=options,
            debug=debug,
        )

        # ======= 2. 基于 option.mode 进行分支判断 =======
        if options.mode == SearchMode.FAST:
            # 2.1 快速模式：直接返回
            return raw_hits

        # 2.2.0 计算 confidence；
        raw_confidence = self._estimate_confidence(
            fts_results=ranked_lists[0].items,
            vector_results=ranked_lists[1].items,
            raw_hits=raw_hits,
            debug=debug,
        )

        if options.mode == SearchMode.ADAPTIVE and self._is_confident_enough(
            raw_confidence, options
        ):
            # 2.2 自适应模式：据 raw search 结果的质量判断是否直接返回
            return raw_hits

        # ======= 3. FULL search 阶段 =======
        full_hits = await self._full_hybrid_search(
            query=query,
            sources=sources,
            raw_ranked_lists=ranked_lists,  # 复用 raw search 的 ranked list 结果，避免重复计算
            options=options,
            completer=completer,
            debug=debug,
        )

        return full_hits
