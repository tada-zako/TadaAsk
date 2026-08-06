from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, JsonValue, SecretStr

from ..models import QuestionType


class BenchmarkSearchMode(StrEnum):
    FAST = "fast"
    ADAPTIVE = "adaptive"
    FULL = "full"


class QueryExpansionConfig(BaseModel):
    """Model connection used by Adaptive and Full retrieval."""

    provider: str
    model: str
    base_url: str | None = None
    api_key: SecretStr | None = Field(default=None, exclude=True)


class RecallRunConfig(BaseModel):
    """Operator-controlled configuration for one recall run."""

    bundle_dir: Path
    workspace_dir: Path
    run_dir: Path
    mode: BenchmarkSearchMode
    rebuild_workspace: bool = False
    resume: bool = True
    case_ids: list[str] = Field(default_factory=list)
    requests_per_minute: int = 20
    max_model_calls_total: int | None = 100
    max_attempts: int = 3
    retry_base_seconds: float = 2.0

    app_settings: dict[str, JsonValue] = Field(default_factory=dict)
    search_options: dict[str, JsonValue] = Field(default_factory=dict)
    query_expansion: QueryExpansionConfig | None = None


class RetrievedChunk(BaseModel):
    """Stable retrieval result exposed by a benchmark runtime."""

    rank: int
    document_id: str | None
    chunk_id: int
    content: str
    rrf_score: float | None = None
    rerank_score: float | None = None


class RetrievalOutcome(BaseModel):
    """Application-neutral result of one retrieval request."""

    chunks: list[RetrievedChunk]
    model_call_attempts: int = 0


class RetrievalRecord(BaseModel):
    """Completed recall checkpoint for one case and search mode."""

    case_id: str
    dataset: str
    question_type: QuestionType
    mode: BenchmarkSearchMode
    query: str
    gold_document_ids: list[str]
    document_recall: dict[str, float]
    evidence_recall: dict[str, float]
    retrieved: list[RetrievedChunk]
    model_call_attempts: int = 0


class ModelCallRecord(BaseModel):
    """One persistent event in the controlled structured-model call ledger."""

    case_id: str
    mode: BenchmarkSearchMode
    attempt: int
    status: Literal["started", "succeeded", "failed"]
    timestamp: datetime
    error: str | None = None
