from dataclasses import dataclass

from pydantic import BaseModel, Field, ConfigDict
from pydantic.alias_generators import to_camel

from app.rag import ExpandedQuery


@dataclass
class RawSearchConfidence:
    """raw search 结果的质量评估结构体"""

    hit_count: int
    fts_count: int
    vector_count: int
    common_overlap_count: int  # FTS & vector 的重叠结果
    rerank_overlap_count: int  # (FTS & vector) 与 rerank 结果的重叠数量
    hit_top_score: float | None = None
    hit_gap: float | None = None


class SearchDebugInfo(BaseModel):
    """搜索调试信息结构体"""

    expanded_queries: ExpandedQuery | None = None
    candidate_counts: dict[str, int] = Field(default_factory=dict)
    latency_ms: dict[str, float] = Field(default_factory=dict)
    confidence: RawSearchConfidence | None = None

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )
