import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from ..models import BenchmarkCase
from .schemas import BenchmarkSearchMode, RetrievalRecord, RetrievedChunk


RECALL_K = (1, 3, 5)


def score_retrieval(
    case: BenchmarkCase,
    chunks: list[RetrievedChunk],
) -> tuple[dict[str, float], dict[str, float]]:
    """Calculate document and exact-evidence recall for one case."""
    gold_document_ids = {evidence.document_id for evidence in case.gold_evidence}
    normalized_evidence = [
        (evidence.document_id, " ".join(evidence.text.split()).casefold())
        for evidence in case.gold_evidence
    ]
    document_recall: dict[str, float] = {}
    evidence_recall: dict[str, float] = {}

    for k in RECALL_K:
        hits = chunks[:k]
        retrieved_document_ids = {hit.document_id for hit in hits}
        document_recall[str(k)] = len(
            gold_document_ids.intersection(retrieved_document_ids)
        ) / len(gold_document_ids)
        matched_evidence = sum(
            any(
                hit.document_id == document_id
                and evidence_text in " ".join(hit.content.split()).casefold()
                for hit in hits
            )
            for document_id, evidence_text in normalized_evidence
        )
        evidence_recall[str(k)] = matched_evidence / len(normalized_evidence)

    return document_recall, evidence_recall


def load_checkpoints(path: Path, *, resume: bool) -> list[RetrievalRecord]:
    """Load successful case checkpoints for a resumed run."""
    if not resume or not path.is_file():
        return []
    with path.open("r", encoding="utf-8") as handle:
        return [RetrievalRecord.model_validate_json(line) for line in handle]


def append_checkpoint(path: Path, record: RetrievalRecord) -> None:
    """Persist one completed case before the workflow advances."""
    with path.open("a", encoding="utf-8", newline="\n") as output:
        output.write(record.model_dump_json(exclude_defaults=True) + "\n")


def summarize_records(
    records: Sequence[RetrievalRecord], mode: BenchmarkSearchMode
) -> dict[str, Any]:
    """Aggregate recall checkpoints without exposing retrieved content."""
    mode_records = [record for record in records if record.mode == mode]
    mode_summary: dict[str, Any] = {"case_count": len(mode_records)}
    for metric in ("document_recall", "evidence_recall"):
        mode_summary[metric] = {
            f"@{k}": (
                sum(getattr(record, metric)[str(k)] for record in mode_records)
                / len(mode_records)
                if mode_records
                else 0.0
            )
            for k in RECALL_K
        }
    return {"modes": {mode.value: mode_summary}}


def write_summary(path: Path, summary: dict[str, Any]) -> None:
    """Write the aggregate result as the only human-facing JSON artifact."""
    path.write_text(
        json.dumps(summary, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
