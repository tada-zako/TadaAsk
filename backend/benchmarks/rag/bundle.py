from collections import Counter
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from .models import (
    BenchmarkCase,
    BenchmarkDatasetConfig,
    BenchmarkDocument,
    DocumentFormat,
    QuestionType,
)


RecordT = TypeVar("RecordT", bound=BaseModel)


def load_jsonl(path: Path, record_type: type[RecordT]) -> list[RecordT]:
    """Load a controlled JSONL manifest into Pydantic records.

    Args:
        path: Manifest file to read.
        record_type: Pydantic model used for each non-empty line.

    Returns:
        Parsed records in manifest order.
    """
    with path.open("r", encoding="utf-8") as handle:
        return [
            record_type.model_validate_json(line) for line in handle if line.strip()
        ]


def load_config(path: Path) -> BenchmarkDatasetConfig:
    """Load one benchmark dataset configuration.

    Args:
        path: JSON configuration file.

    Returns:
        Parsed benchmark configuration.
    """
    return BenchmarkDatasetConfig.model_validate_json(path.read_text(encoding="utf-8"))


def summarize_bundle(
    cases: list[BenchmarkCase], documents: list[BenchmarkDocument]
) -> dict[str, Any]:
    """Calculate the aggregate distribution used by benchmark reports.

    Args:
        cases: Materialized benchmark cases.
        documents: Materialized corpus documents.

    Returns:
        Aggregate counts without question, answer, or document content.
    """
    unanswerable_count = sum(
        case.question_type == QuestionType.UNANSWERABLE for case in cases
    )
    return {
        "case_count": len(cases),
        "document_count": len(documents),
        "answerable_count": len(cases) - unanswerable_count,
        "unanswerable_count": unanswerable_count,
        "cases_by_language": dict(
            sorted(Counter(case.language.value for case in cases).items())
        ),
        "cases_by_question_type": dict(
            sorted(Counter(case.question_type.value for case in cases).items())
        ),
        "cases_by_dataset": dict(
            sorted(Counter(case.dataset for case in cases).items())
        ),
        "documents_by_format": dict(
            sorted(
                Counter(
                    document.document_format.value for document in documents
                ).items()
            )
        ),
        "documents_by_language": dict(
            sorted(Counter(document.language.value for document in documents).items())
        ),
        "distractor_document_count": sum(
            document.is_distractor for document in documents
        ),
    }


def audit_bundle(bundle_dir: Path, config_path: Path) -> dict[str, Any]:
    """Check the ground-truth links and frozen counts of one bundle.

    Args:
        bundle_dir: Directory containing cases.jsonl, documents.jsonl, and corpus.
        config_path: Configuration containing the expected aggregate counts.

    Returns:
        Aggregate bundle summary.

    Raises:
        ValueError: An evidence reference or frozen expectation is inconsistent.
    """
    config = load_config(config_path)
    cases = load_jsonl(bundle_dir / "cases.jsonl", BenchmarkCase)
    documents = load_jsonl(bundle_dir / "documents.jsonl", BenchmarkDocument)
    documents_by_id = {document.id: document for document in documents}

    for document in documents:
        document_path = bundle_dir / document.relative_path
        if not document_path.is_file():
            raise ValueError(f"document file is missing: {document.id}")

    validation_texts: dict[str, str] = {}
    # Evidence validity changes benchmark scores, so referenced text is checked
    # once when a controlled bundle is built or explicitly validated.
    for case in cases:
        for evidence in case.gold_evidence:
            document = documents_by_id.get(evidence.document_id)
            if document is None:
                raise ValueError(
                    f"case {case.id} references unknown document {evidence.document_id}"
                )
            validation_path = document.validation_text_path
            if (
                validation_path is None
                and document.document_format == DocumentFormat.MARKDOWN
            ):
                validation_path = document.relative_path
            if validation_path is not None:
                validation_text = validation_texts.get(document.id)
                if validation_text is None:
                    validation_text = (bundle_dir / validation_path).read_text(
                        encoding="utf-8"
                    )
                    validation_texts[document.id] = validation_text
                expected = " ".join(evidence.text.split()).casefold()
                actual = " ".join(validation_text.split()).casefold()
                if expected not in actual:
                    raise ValueError(
                        f"evidence for case {case.id} was not found in {document.id}"
                    )

    summary = summarize_bundle(cases, documents)
    for name, expected in config.expectations.items():
        if summary.get(name) != expected:
            raise ValueError(
                f"dataset expectation mismatch for {name}: "
                f"expected {expected}, got {summary.get(name)}"
            )
    return summary
