"""Versioned data contracts shared by the RAG benchmark stages."""

from datetime import datetime
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.constants import SearchMode
from app.db.schemas import HybridSearchOptions


SCHEMA_VERSION = 1
RecordId = str


class StrictModel(BaseModel):
    """Reject unknown fields so stale benchmark artifacts fail early."""

    model_config = ConfigDict(extra="forbid")


class VersionedRecord(StrictModel):
    schema_version: Literal[1] = SCHEMA_VERSION


class BenchmarkLanguage(StrEnum):
    ZH = "zh"
    EN = "en"
    MIXED = "mixed"


class QuestionType(StrEnum):
    DIRECT = "direct"
    PARAPHRASE = "paraphrase"
    EXACT = "exact"
    UNANSWERABLE = "unanswerable"
    MULTI_TURN = "multi_turn"
    MULTI_DOCUMENT = "multi_document"


class DocumentFormat(StrEnum):
    MARKDOWN = "markdown"
    TEXT = "text"
    PDF = "pdf"
    HTML = "html"
    DOCX = "docx"


class ConversationRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class RunStage(StrEnum):
    RETRIEVAL = "retrieval"
    END_TO_END = "end_to_end"


class RunStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class JudgeVerdict(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    REVIEW = "review"


class ConversationTurn(StrictModel):
    role: ConversationRole
    content: str = Field(min_length=1)


class GoldEvidence(StrictModel):
    document_id: RecordId = Field(min_length=1)
    text: str = Field(min_length=1)
    section_header: str | None = None
    page_number: int | None = Field(default=None, ge=1)


class BenchmarkCase(VersionedRecord):
    """One versioned question and its human-auditable ground truth."""

    id: RecordId = Field(pattern=r"^[a-z0-9][a-z0-9._-]*$")
    dataset: str = Field(min_length=1)
    dataset_split: str = Field(min_length=1)
    language: BenchmarkLanguage
    question_type: QuestionType
    question: str = Field(min_length=1)
    is_answerable: bool = True
    expected_answer: str | None = None
    acceptable_answers: list[str] = Field(default_factory=list)
    gold_evidence: list[GoldEvidence] = Field(default_factory=list)
    conversation_history: list[ConversationTurn] = Field(default_factory=list)
    standalone_enabled: bool = False
    expected_standalone_query: str | None = None
    tags: list[str] = Field(default_factory=list)

    @field_validator("acceptable_answers", "tags")
    @classmethod
    def reject_blank_list_items(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("list items must not be blank")
        return value

    @model_validator(mode="after")
    def validate_ground_truth(self) -> "BenchmarkCase":
        if self.is_answerable:
            if not self.expected_answer or not self.expected_answer.strip():
                raise ValueError("answerable cases require expected_answer")
            if not self.gold_evidence:
                raise ValueError("answerable cases require gold_evidence")
            if self.question_type == QuestionType.UNANSWERABLE:
                raise ValueError("answerable cases cannot use the unanswerable type")
        else:
            if self.question_type != QuestionType.UNANSWERABLE:
                raise ValueError("unanswerable cases must use the unanswerable type")
            if self.expected_answer is not None:
                raise ValueError("unanswerable cases cannot define expected_answer")
            if self.acceptable_answers:
                raise ValueError("unanswerable cases cannot define acceptable_answers")
            if self.gold_evidence:
                raise ValueError("unanswerable cases cannot define gold_evidence")

        if self.question_type == QuestionType.MULTI_TURN:
            if not self.conversation_history:
                raise ValueError("multi-turn cases require conversation_history")
            if not self.standalone_enabled:
                raise ValueError("multi-turn cases must enable standalone rewriting")
            if not self.expected_standalone_query:
                raise ValueError("multi-turn cases require expected_standalone_query")

        if self.question_type == QuestionType.MULTI_DOCUMENT:
            document_ids = {item.document_id for item in self.gold_evidence}
            if len(document_ids) < 2:
                raise ValueError(
                    "multi-document cases require at least two gold documents"
                )

        return self


class BenchmarkDocument(VersionedRecord):
    """Stable document metadata; content remains in the referenced local file."""

    id: RecordId = Field(pattern=r"^[a-z0-9][a-z0-9._-]*$")
    dataset: str = Field(min_length=1)
    dataset_split: str = Field(min_length=1)
    title: str = Field(min_length=1)
    filename: str = Field(min_length=1)
    language: BenchmarkLanguage
    document_format: DocumentFormat
    relative_path: str = Field(min_length=1)
    validation_text_path: str | None = None
    license: str = Field(min_length=1)
    source_url: str | None = None
    sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    is_distractor: bool = False
    tags: list[str] = Field(default_factory=list)

    @field_validator("relative_path", "validation_text_path")
    @classmethod
    def require_safe_relative_path(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.replace("\\", "/")
        path = PurePosixPath(normalized)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("benchmark paths must stay relative to the benchmark root")
        return path.as_posix()

    @model_validator(mode="after")
    def validate_filename_and_format(self) -> "BenchmarkDocument":
        if PurePosixPath(self.relative_path).name != self.filename:
            raise ValueError("filename must match the relative_path basename")

        allowed_suffixes = {
            DocumentFormat.MARKDOWN: {".md"},
            DocumentFormat.TEXT: {".txt"},
            DocumentFormat.PDF: {".pdf"},
            DocumentFormat.HTML: {".html", ".htm"},
            DocumentFormat.DOCX: {".docx"},
        }
        suffix = PurePosixPath(self.filename).suffix.lower()
        if suffix not in allowed_suffixes[self.document_format]:
            raise ValueError("document_format does not match the filename suffix")
        return self


class RunnerLimits(StrictModel):
    """Safety defaults for later live runners; live execution starts disabled."""

    live_execution_enabled: bool = False
    concurrency: int = Field(default=3, ge=1, le=20)
    max_retries: int = Field(default=5, ge=0, le=10)
    request_timeout_seconds: float = Field(default=120.0, gt=0)
    budget_warning_usd: float = Field(default=25.0, ge=0)
    budget_hard_limit_usd: float = Field(default=30.0, gt=0)

    @model_validator(mode="after")
    def validate_budget_limits(self) -> "RunnerLimits":
        if self.budget_warning_usd >= self.budget_hard_limit_usd:
            raise ValueError("budget warning must be below the hard limit")
        return self


class BenchmarkRunConfig(VersionedRecord):
    """Frozen inputs for a benchmark run; mode overwrites the template mode."""

    name: str = Field(min_length=1)
    case_manifest: str = Field(min_length=1)
    document_manifest: str = Field(min_length=1)
    modes: list[SearchMode] = Field(min_length=1)
    rag_options_template: HybridSearchOptions = Field(
        default_factory=HybridSearchOptions
    )
    generation_model_profile_uid: str | None = None
    judge_model_profile_uid: str | None = None
    runner: RunnerLimits = Field(default_factory=RunnerLimits)

    @field_validator("case_manifest", "document_manifest")
    @classmethod
    def require_safe_manifest_path(cls, value: str) -> str:
        normalized = value.replace("\\", "/")
        path = PurePosixPath(normalized)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("manifest paths must stay relative to the benchmark root")
        return path.as_posix()

    @field_validator("modes")
    @classmethod
    def reject_duplicate_modes(cls, value: list[SearchMode]) -> list[SearchMode]:
        if len(value) != len(set(value)):
            raise ValueError("modes must not contain duplicates")
        return value


class RetrievalHit(StrictModel):
    rank: int = Field(ge=1)
    document_id: RecordId | None = None
    source_item_uid: str | None = None
    chunk_id: int | None = None
    excerpt: str = ""
    section_header: str | None = None
    rrf_score: float | None = None
    rerank_score: float | None = None


class CitationRecord(StrictModel):
    citation_id: int = Field(ge=1)
    document_id: RecordId | None = None
    source_item_uid: str | None = None
    chunk_id: int | None = None
    excerpt: str = ""


class TokenUsageRecord(StrictModel):
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    reasoning_tokens: int = Field(default=0, ge=0)
    cache_read_tokens: int = Field(default=0, ge=0)
    cache_write_tokens: int = Field(default=0, ge=0)


class BenchmarkRunResult(VersionedRecord):
    """Raw result produced by either the retrieval or end-to-end runner."""

    run_id: str = Field(min_length=1)
    case_id: RecordId = Field(min_length=1)
    stage: RunStage
    requested_mode: SearchMode
    actual_mode: SearchMode | None = None
    status: RunStatus
    started_at: datetime
    completed_at: datetime | None = None
    model_profile_uid: str | None = None
    standalone_query: str | None = None
    retrieval_hits: list[RetrievalHit] = Field(default_factory=list)
    answer: str | None = None
    citations: list[CitationRecord] = Field(default_factory=list)
    latency_ms: dict[str, float] = Field(default_factory=dict)
    token_usage: TokenUsageRecord | None = None
    estimated_cost_usd: float | None = Field(default=None, ge=0)
    error: str | None = None

    @field_validator("latency_ms")
    @classmethod
    def reject_negative_latency(cls, value: dict[str, float]) -> dict[str, float]:
        if any(item < 0 for item in value.values()):
            raise ValueError("latency values must not be negative")
        return value

    @model_validator(mode="after")
    def validate_status_payload(self) -> "BenchmarkRunResult":
        if self.completed_at and self.completed_at < self.started_at:
            raise ValueError("completed_at must not precede started_at")
        if self.status == RunStatus.FAILED and not self.error:
            raise ValueError("failed results require an error")
        if self.status == RunStatus.COMPLETED:
            if not self.completed_at:
                raise ValueError("completed results require completed_at")
            if self.stage == RunStage.END_TO_END and self.answer is None:
                raise ValueError("completed end-to-end results require an answer")
        return self


class JudgeScores(StrictModel):
    correctness: int = Field(ge=0, le=4)
    faithfulness: int = Field(ge=0, le=4)
    relevance: int = Field(ge=0, le=4)
    citation_support: int | None = Field(default=None, ge=0, le=4)
    citation_completeness: int | None = Field(default=None, ge=0, le=4)
    abstention_correct: bool | None = None


class JudgeResult(VersionedRecord):
    """Normalized structured output from the benchmark judge model."""

    run_id: str = Field(min_length=1)
    case_id: RecordId = Field(min_length=1)
    mode: SearchMode
    judge_model_profile_uid: str = Field(min_length=1)
    scores: JudgeScores
    verdict: JudgeVerdict
    reasons: list[str] = Field(min_length=1)
    needs_human_review: bool = False
    created_at: datetime
    token_usage: TokenUsageRecord | None = None
    estimated_cost_usd: float | None = Field(default=None, ge=0)

    @field_validator("reasons")
    @classmethod
    def reject_blank_reasons(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("judge reasons must not be blank")
        return value
