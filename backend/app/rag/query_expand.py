from pydantic import BaseModel, Field

from app.providers import (
    StructuredCompleter,
    Message,
    ModelSettings,
    QUERY_EXPAND_USER_TEMPLATE,
    QUERY_EXPAND_SYSTEM_PROMPT,
)
from app.utils import TTLCache, normalize_text, stable_hash
from app.core.constants import ChatMessageRole


class ExpandedQuery(BaseModel):
    """Schema for expanded query generation to improve information retrieval."""

    keywords: list[str] = Field(
        ...,
        description="A list of key terms, entities, or core concepts extracted directly from the original user query.",
    )
    alternative_queries: list[str] = Field(
        ...,
        description="A list of reformulated or paraphrased search queries derived from the original query, designed to improve search recall and cover different phrasing.",
    )
    hypothetical_document: str = Field(
        ...,
        description="A synthesized, hypothetical paragraph or document that directly answers the original query, simulating the ideal search target to improve semantic retrieval.",
    )


class QueryExpander:
    """查询扩展器"""

    def __init__(
        self,
        *,
        prompt_version: str = "prompt_v1",
        cache_enabled: bool = True,
        cache_size: int = 512,
        ttl_seconds: int = 3600,
    ):
        self._prompt_version = prompt_version
        self._cache_enabled = cache_enabled

        if self._cache_enabled:
            self._cache = TTLCache[str, ExpandedQuery](
                max_size=cache_size, ttl_seconds=ttl_seconds
            )

    def _cache_key(
        self,
        *,
        query: str,
        max_keywords: int,
        max_alternative_queries: int,
        completer: StructuredCompleter,
    ) -> str:
        """生成缓存键；基于查询文本和参数的规范化和稳定哈希"""
        return stable_hash(
            {
                "kind": "expanded_query",
                "model": completer.model_name,
                "prompt_version": self._prompt_version,
                "query": normalize_text(query),
                "max_keywords": max_keywords,
                "max_alternative_queries": max_alternative_queries,
            }
        )

    async def expand_query(
        self,
        query: str,
        *,
        max_keywords: int = 5,
        max_alternative_queries: int = 2,
        completer: StructuredCompleter,
    ) -> ExpandedQuery:
        """
        生成扩展查询

        Args:
            query (str): 原始用户查询
            max_keywords (int): 关键词扩展的最大数量
            max_alternative_queries (int): 改写查询的最大数量

        Returns:
            ExpandedQuery: 包含关键词、改写查询和假设文档的扩展查询结果
        """
        if max_keywords < 1:
            raise ValueError("max_keywords must be greater than 0")
        if max_alternative_queries < 1:
            raise ValueError("max_alternative_queries must be greater than 0")

        if self._cache_enabled:
            # 检查缓存结果
            key = self._cache_key(
                query=query,
                max_keywords=max_keywords,
                max_alternative_queries=max_alternative_queries,
                completer=completer,
            )
            cached_result = self._cache.get(key)
            if cached_result is not None:
                return cached_result

        messages = [
            Message(
                role=ChatMessageRole.SYSTEM,
                content=QUERY_EXPAND_SYSTEM_PROMPT,
            ),
            Message(
                role=ChatMessageRole.USER,
                content=QUERY_EXPAND_USER_TEMPLATE.format(
                    query=query,
                    max_keywords=max_keywords,
                    max_alternative_queries=max_alternative_queries,
                ),
            ),
        ]

        result: ExpandedQuery = await completer.complete_structured(
            messages=messages,
            model_settings=ModelSettings.for_query_expansion(),
            schema=ExpandedQuery,
        )

        expanded = ExpandedQuery(
            keywords=result.keywords[:max_keywords],
            alternative_queries=result.alternative_queries[:max_alternative_queries],
            hypothetical_document=result.hypothetical_document,
        )

        # 设置缓存结果
        if self._cache_enabled:
            self._cache.set(key, expanded)  # type: ignore

        return expanded
