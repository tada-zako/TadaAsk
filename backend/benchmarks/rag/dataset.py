"""Streaming validation helpers for benchmark manifests and local fixtures."""

import json
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from .schemas import BenchmarkCase, BenchmarkDocument, BenchmarkRunConfig, StrictModel


RecordT = TypeVar("RecordT", bound=BaseModel)


class BenchmarkDataError(ValueError):
    """A compact validation error that never embeds complete input records."""


class DatasetSummary(StrictModel):
    case_count: int
    document_count: int
    answerable_count: int
    unanswerable_count: int
    cases_by_language: dict[str, int]
    cases_by_question_type: dict[str, int]
    cases_by_dataset: dict[str, int]
    documents_by_format: dict[str, int]


def _compact_validation_error(exc: ValidationError) -> str:
    parts: list[str] = []
    for item in exc.errors(include_input=False):
        location = ".".join(str(part) for part in item["loc"])
        parts.append(f"{location}: {item['msg']}")
    return "; ".join(parts)


def iter_jsonl(path: Path, record_type: type[RecordT]) -> Iterator[RecordT]:
    """Parse one record at a time without printing or retaining the raw dataset."""
    try:
        handle = path.open("r", encoding="utf-8")
    except OSError as exc:
        raise BenchmarkDataError(f"cannot open manifest: {path}") from exc

    with handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                raw: Any = json.loads(line)
                yield record_type.model_validate(raw)
            except json.JSONDecodeError as exc:
                raise BenchmarkDataError(
                    f"invalid JSON at {path}:{line_number}"
                ) from exc
            except ValidationError as exc:
                details = _compact_validation_error(exc)
                raise BenchmarkDataError(
                    f"invalid record at {path}:{line_number}: {details}"
                ) from exc


def load_run_config(path: Path) -> BenchmarkRunConfig:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return BenchmarkRunConfig.model_validate(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise BenchmarkDataError(f"cannot read config: {path}") from exc
    except ValidationError as exc:
        details = _compact_validation_error(exc)
        raise BenchmarkDataError(f"invalid config at {path}: {details}") from exc


def _resolve_inside(root: Path, relative_path: str) -> Path:
    root = root.resolve()
    resolved = (root / relative_path).resolve()
    if not resolved.is_relative_to(root):
        raise BenchmarkDataError(f"path escapes benchmark root: {relative_path}")
    return resolved


def _normalize_text(value: str) -> str:
    return " ".join(value.split()).casefold()


def _read_validation_text(root: Path, document: BenchmarkDocument) -> str | None:
    validation_path = document.validation_text_path
    if validation_path is None and document.document_format.value in {
        "markdown",
        "text",
        "html",
    }:
        validation_path = document.relative_path
    if validation_path is None:
        return None

    path = _resolve_inside(root, validation_path)
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise BenchmarkDataError(
            f"cannot read validation text for document: {document.id}"
        ) from exc


def validate_bundle(config_path: Path) -> DatasetSummary:
    """Validate cross-file references and return counts only, never record content."""
    config_path = config_path.resolve()
    root = Path(__file__).resolve().parent
    config = load_run_config(config_path)
    case_manifest = _resolve_inside(root, config.case_manifest)
    document_manifest = _resolve_inside(root, config.document_manifest)

    documents: dict[str, BenchmarkDocument] = {}
    documents_by_format: Counter[str] = Counter()
    for document in iter_jsonl(document_manifest, BenchmarkDocument):
        if document.id in documents:
            raise BenchmarkDataError(f"duplicate document id: {document.id}")
        source_path = _resolve_inside(root, document.relative_path)
        if not source_path.is_file():
            raise BenchmarkDataError(f"document file is missing: {document.id}")
        if document.validation_text_path:
            validation_path = _resolve_inside(root, document.validation_text_path)
            if not validation_path.is_file():
                raise BenchmarkDataError(
                    f"validation text is missing for document: {document.id}"
                )
        documents[document.id] = document
        documents_by_format[document.document_format.value] += 1

    if not documents:
        raise BenchmarkDataError("document manifest must not be empty")

    case_ids: set[str] = set()
    cases_by_language: Counter[str] = Counter()
    cases_by_question_type: Counter[str] = Counter()
    cases_by_dataset: Counter[str] = Counter()
    answerable_count = 0
    unanswerable_count = 0

    for case in iter_jsonl(case_manifest, BenchmarkCase):
        if case.id in case_ids:
            raise BenchmarkDataError(f"duplicate case id: {case.id}")
        case_ids.add(case.id)
        cases_by_language[case.language.value] += 1
        cases_by_question_type[case.question_type.value] += 1
        cases_by_dataset[case.dataset] += 1

        if case.is_answerable:
            answerable_count += 1
        else:
            unanswerable_count += 1

        for evidence in case.gold_evidence:
            document = documents.get(evidence.document_id)
            if document is None:
                raise BenchmarkDataError(
                    f"case {case.id} references unknown document {evidence.document_id}"
                )
            validation_text = _read_validation_text(root, document)
            if validation_text is None:
                continue
            if _normalize_text(evidence.text) not in _normalize_text(validation_text):
                raise BenchmarkDataError(
                    f"gold evidence for case {case.id} was not found in "
                    f"document {document.id}"
                )

    if not case_ids:
        raise BenchmarkDataError("case manifest must not be empty")

    return DatasetSummary(
        case_count=len(case_ids),
        document_count=len(documents),
        answerable_count=answerable_count,
        unanswerable_count=unanswerable_count,
        cases_by_language=dict(sorted(cases_by_language.items())),
        cases_by_question_type=dict(sorted(cases_by_question_type.items())),
        cases_by_dataset=dict(sorted(cases_by_dataset.items())),
        documents_by_format=dict(sorted(documents_by_format.items())),
    )
