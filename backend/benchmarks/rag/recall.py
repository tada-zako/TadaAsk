import json
import sys
import tomllib
from pathlib import Path
from typing import Any

from loguru import logger

from .bundle import load_jsonl
from .models import BenchmarkCase, BenchmarkDocument, QuestionType
from .runner import (
    BenchmarkSearchMode,
    RecallRunConfig,
    RetrievalRecord,
    RetrievalRuntime,
    RetrievedChunk,
    TadaAskRuntime,
)


PACKAGE_ROOT = Path(__file__).resolve().parent
BACKEND_ROOT = PACKAGE_ROOT.parents[1]
RECALL_K = (1, 3, 5)


def load_recall_config(path: Path) -> RecallRunConfig:
    """Load a benchmark TOML file and resolve its runtime paths.

    Args:
        path: TOML file edited by the benchmark operator.

    Returns:
        Configuration with paths resolved from the backend directory.
    """
    with path.open("rb") as handle:
        raw = tomllib.load(handle)

    benchmark = raw["benchmark"]

    def resolve(value: str) -> Path:
        candidate = Path(value)
        return (
            candidate.resolve()
            if candidate.is_absolute()
            else (BACKEND_ROOT / candidate).resolve()
        )

    return RecallRunConfig.model_validate(
        {
            **benchmark,
            "bundle_dir": resolve(benchmark["bundle_dir"]),
            "workspace_dir": resolve(benchmark["workspace_dir"]),
            "run_dir": resolve(benchmark["run_dir"]),
            "app_settings": raw.get("app", {}),
            "search_options": raw.get("search", {}),
            "query_expansion": raw.get("query_expansion", {}),
        }
    )


def _score_results(
    *,
    case: BenchmarkCase,
    results: list[RetrievedChunk],
) -> tuple[dict[str, float], dict[str, float]]:
    """Calculate document and exact-evidence recall over ranked chunks.

    Args:
        case: Answerable benchmark case with gold evidence.
        results: Ranked HybridSearchResult objects.
    Returns:
        Document Recall@1/@3/@5 and Evidence Recall@1/@3/@5.
    """
    gold_document_ids = {evidence.document_id for evidence in case.gold_evidence}
    normalized_evidence = [
        (evidence.document_id, " ".join(evidence.text.split()).casefold())
        for evidence in case.gold_evidence
    ]
    document_recall: dict[str, float] = {}
    evidence_recall: dict[str, float] = {}

    for k in RECALL_K:
        hits = results[:k]
        retrieved_document_ids = {hit.document_id for hit in hits}
        document_recall[str(k)] = len(
            gold_document_ids.intersection(retrieved_document_ids)
        ) / len(gold_document_ids)

        matched_evidence = 0
        for document_id, evidence_text in normalized_evidence:
            if any(
                hit.document_id == document_id
                and evidence_text in " ".join(hit.content.split()).casefold()
                for hit in hits
            ):
                matched_evidence += 1
        evidence_recall[str(k)] = matched_evidence / len(normalized_evidence)

    return document_recall, evidence_recall


def _summarize_results(path: Path, modes: tuple[str, ...]) -> dict[str, Any]:
    """Aggregate checkpoint records without loading document content into stdout."""
    records_by_mode: dict[str, list[RetrievalRecord]] = {mode: [] for mode in modes}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            record = RetrievalRecord.model_validate_json(line)
            if record.mode.value in records_by_mode:
                records_by_mode[record.mode.value].append(record)

    summary: dict[str, Any] = {"modes": {}}
    for mode, records in records_by_mode.items():
        mode_summary: dict[str, Any] = {"case_count": len(records)}
        for metric in ("document_recall", "evidence_recall"):
            mode_summary[metric] = {
                f"@{k}": (
                    sum(getattr(record, metric)[str(k)] for record in records)
                    / len(records)
                    if records
                    else 0.0
                )
                for k in RECALL_K
            }
        summary["modes"][mode] = mode_summary
    return summary


async def _run_retrieval_cases(
    *,
    config: RecallRunConfig,
    cases: list[BenchmarkCase],
    modes: tuple[BenchmarkSearchMode, ...],
    runtime: RetrievalRuntime,
) -> Path:
    """Search answerable cases sequentially and checkpoint each mode result."""
    results_path = config.run_dir / "recall.jsonl"
    completed: set[tuple[str, str]] = set()
    if config.resume and results_path.is_file():
        with results_path.open("r", encoding="utf-8") as handle:
            completed = {
                (record["case_id"], record["mode"])
                for line in handle
                if (record := json.loads(line))
            }
    elif results_path.exists():
        results_path.write_text("", encoding="utf-8")

    with results_path.open("a", encoding="utf-8", newline="\n") as output:
        for case in cases:
            if case.question_type == QuestionType.UNANSWERABLE:
                continue
            # Retrieval is evaluated after standalone rewriting, not as a test
            # of the conversation rewriter itself.
            query = case.expected_standalone_query or case.question
            for mode in modes:
                key = (case.id, mode.value)
                if key in completed:
                    continue
                results = await runtime.retrieve(
                    query=query,
                    mode=mode,
                    search_options=config.search_options,
                )
                document_recall, evidence_recall = _score_results(
                    case=case,
                    results=results,
                )
                record = RetrievalRecord(
                    case_id=case.id,
                    dataset=case.dataset,
                    question_type=case.question_type,
                    mode=mode,
                    query=query,
                    gold_document_ids=sorted(
                        {evidence.document_id for evidence in case.gold_evidence}
                    ),
                    document_recall=document_recall,
                    evidence_recall=evidence_recall,
                    retrieved=results,
                )
                output.write(record.model_dump_json(exclude_defaults=True) + "\n")
                output.flush()
    return results_path


async def run_recall(config_path: Path) -> dict[str, Any]:
    """Run the in-process TadaAsk retrieval recall benchmark.

    The function deliberately avoids importing app modules until benchmark paths
    are bound, then assembles the same indexing and search components as the app.

    Args:
        config_path: Operator-managed recall TOML configuration.

    Returns:
        Aggregate recall metrics and artifact paths.
    """
    logger.remove()
    logger.add(sys.stderr, level="WARNING")
    config = load_recall_config(config_path)
    modes = config.modes
    if max(RECALL_K) > config.search_options.get("top_k", 8):
        raise ValueError("search.top_k must be at least 5 for Recall@5")
    if any(mode != BenchmarkSearchMode.FAST for mode in modes):
        missing = {"provider", "model"}.difference(config.query_expansion)
        if missing:
            raise ValueError(
                "query_expansion.provider and query_expansion.model are required "
                "for adaptive/full recall"
            )

    cases = load_jsonl(config.bundle_dir / "cases.jsonl", BenchmarkCase)
    documents = load_jsonl(config.bundle_dir / "documents.jsonl", BenchmarkDocument)
    runtime = await TadaAskRuntime.create(config)
    try:
        await runtime.prepare_corpus(
            bundle_dir=config.bundle_dir,
            documents=documents,
        )
        results_path = await _run_retrieval_cases(
            config=config,
            cases=cases,
            modes=modes,
            runtime=runtime,
        )
    finally:
        await runtime.close()

    # The CLI prints only this aggregate summary; chunk content stays in JSONL.
    summary = _summarize_results(results_path, tuple(mode.value for mode in modes))
    summary.update(
        {
            "answerable_case_count": sum(
                case.question_type != QuestionType.UNANSWERABLE for case in cases
            ),
            "skipped_unanswerable_count": sum(
                case.question_type == QuestionType.UNANSWERABLE for case in cases
            ),
            "results_path": str(results_path),
            "workspace_dir": str(config.workspace_dir),
        }
    )
    summary_path = config.run_dir / "recall-summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {**summary, "summary_path": str(summary_path)}
