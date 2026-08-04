from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class BenchmarkLanguage(StrEnum):
    """Benchmark 测试集的语言类型"""

    ZH = "zh"
    EN = "en"
    MIXED = "mixed"


class QuestionType(StrEnum):
    """Benchmark 测试集的问题类型"""

    DIRECT = "direct"
    PARAPHRASE = "paraphrase"
    EXACT = "exact"
    UNANSWERABLE = "unanswerable"
    MULTI_TURN = "multi_turn"
    MULTI_DOCUMENT = "multi_document"


class DocumentFormat(StrEnum):
    """Benchmark 测试集的文档格式类型"""

    MARKDOWN = "markdown"
    PDF = "pdf"
    HTML = "html"


class ConversationTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class GoldEvidence(BaseModel):
    document_id: str
    text: str


class BenchmarkCase(BaseModel):
    id: str
    dataset: str
    language: BenchmarkLanguage
    question_type: QuestionType
    question: str
    expected_answer: str | None = None
    acceptable_answers: list[str] = Field(default_factory=list)
    gold_evidence: list[GoldEvidence] = Field(default_factory=list)
    conversation_history: list[ConversationTurn] = Field(default_factory=list)
    expected_standalone_query: str | None = None
    needs_review: bool = False


class BenchmarkDocument(BaseModel):
    id: str
    dataset: str
    title: str
    language: BenchmarkLanguage
    document_format: DocumentFormat
    relative_path: str
    validation_text_path: str | None = None
    is_distractor: bool = False


class BenchmarkDatasetConfig(BaseModel):
    expectations: dict[str, int | dict[str, int]] = Field(default_factory=dict)
