from pydantic import BaseModel, Field

from app.providers import (
    StructuredCompleter,
    Message,
    QUERY_EXPAND_USER_TEMPLATE,
    QUERY_EXPAND_SYSTEM_PROMPT,
)


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

    def __init__(self, completer: StructuredCompleter):
        self._completer = completer

    async def expand_query(self, query: str) -> ExpandedQuery:
        """生成扩展查询

        Args:
            query (str): 原始用户查询

        Returns:
            ExpandedQuery: 包含关键词、改写查询和假设文档的扩展查询结果
        """
        messages = [
            Message(
                role="system",
                content=QUERY_EXPAND_SYSTEM_PROMPT,
            ),
            Message(
                role="user", content=QUERY_EXPAND_USER_TEMPLATE.format(query=query)
            ),
        ]

        result: ExpandedQuery = await self._completer.complete_structured(
            messages=messages,
            schema=ExpandedQuery,
        )
        return result
