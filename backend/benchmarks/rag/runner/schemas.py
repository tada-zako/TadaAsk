from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, JsonValue

from ..models import QuestionType


class BenchmarkSearchMode(StrEnum):
    FAST = "fast"
    ADAPTIVE = "adaptive"
    FULL = "full"


class RecallRunConfig(BaseModel):
    """Operator-controlled configuration for one recall run."""

    bundle_dir: Path
    workspace_dir: Path
    run_dir: Path
    modes: tuple[BenchmarkSearchMode, ...] = (BenchmarkSearchMode.FAST,)
    rebuild_workspace: bool = False
    resume: bool = True

    app_settings: dict[str, JsonValue] = Field(default_factory=dict)
    search_options: dict[str, JsonValue] = Field(default_factory=dict)
    query_expansion: dict[str, str] = Field(default_factory=dict)


class RetrievedChunk(BaseModel):
    """Stable retrieval result exposed by a benchmark runtime."""

    rank: int
    document_id: str | None
    chunk_id: int
    content: str
    rrf_score: float | None = None
    rerank_score: float | None = None


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
    model_cache_hits: int = 0


class RunManifest(BaseModel):
    """Identity and progress state used to validate a resumed run."""

    fingerprint: str
    git_commit: str
    created_at: datetime
    status: Literal["running", "partial", "completed"]
    config: RecallRunConfig
    completed_case_count: int = 0
    pending_case_count: int = 0
    model_call_attempts: int = 0


class ModelCallRecord(BaseModel):
    """One persistent event in the controlled structured-model call ledger."""

    call_id: str
    case_id: str
    mode: BenchmarkSearchMode
    request_key: str
    attempt: int
    status: Literal["started", "succeeded", "failed"]
    timestamp: datetime
    schema_name: str
    response: dict[str, JsonValue] | None = None
    error: str | None = None
