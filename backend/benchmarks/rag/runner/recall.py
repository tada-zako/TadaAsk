import json
import os
import re
import sys
import tomllib
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from typing import Any

from loguru import logger

from ..bundle import load_jsonl
from ..models import BenchmarkCase, BenchmarkDocument, QuestionType
from .control import ModelCallController, ModelCallLimitReached
from .protocols import RetrievalRuntime
from .schemas import (
    BenchmarkSearchMode,
    RecallRunConfig,
    RetrievalRecord,
    RetrievedChunk,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PACKAGE_ROOT.parents[1]
RECALL_K = (1, 3, 5)
RuntimeFactory = Callable[
    [RecallRunConfig, ModelCallController | None], Awaitable[RetrievalRuntime]
]


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
    """Calculate document and exact-evidence recall over ranked chunks."""
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


def _summarize_results(
    records: Sequence[RetrievalRecord], mode: BenchmarkSearchMode
) -> dict[str, Any]:
    """Aggregate checkpoint records without exposing retrieved content."""
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


class RecallRunner:
    """Run deterministic recall batches against an injected RAG runtime."""

    def __init__(
        self,
        *,
        config: RecallRunConfig,
        cases: list[BenchmarkCase],
        documents: list[BenchmarkDocument],
        runtime_factory: RuntimeFactory,
    ) -> None:
        self.config = config
        self.cases = cases
        self.documents = documents
        self.runtime_factory = runtime_factory
        self.results_path = config.run_dir / "recall.jsonl"
        self.ledger_path = config.run_dir / "model-calls.jsonl"
        self.summary_path = config.run_dir / "recall-summary.json"

    async def run(self) -> dict[str, Any]:
        """Execute one recoverable batch and write aggregate run state."""
        self.config.run_dir.mkdir(parents=True, exist_ok=True)
        if not self.config.resume:
            for path in (
                self.results_path,
                self.ledger_path,
                self.summary_path,
            ):
                path.unlink(missing_ok=True)

        target_cases = self._select_cases()
        records = self._load_records()
        completed_ids = {
            record.case_id for record in records if record.mode == self.config.mode
        }
        pending_cases = [case for case in target_cases if case.id not in completed_ids]
        controller = self._create_model_controller()

        stopped_by_limit = False
        runtime: RetrievalRuntime | None = None
        try:
            if pending_cases:
                runtime = await self.runtime_factory(self.config, controller)
                await runtime.prepare_corpus(
                    bundle_dir=self.config.bundle_dir,
                    documents=self.documents,
                )

            with self.results_path.open("a", encoding="utf-8", newline="\n") as output:
                for case in pending_cases:
                    try:
                        outcome = await runtime.retrieve(
                            case_id=case.id,
                            query=case.expected_standalone_query or case.question,
                            mode=self.config.mode,
                            search_options=self.config.search_options,
                        )
                    except ModelCallLimitReached:
                        stopped_by_limit = True
                        break

                    document_recall, evidence_recall = _score_results(
                        case=case,
                        results=outcome.chunks,
                    )
                    record = RetrievalRecord(
                        case_id=case.id,
                        dataset=case.dataset,
                        question_type=case.question_type,
                        mode=self.config.mode,
                        query=case.expected_standalone_query or case.question,
                        gold_document_ids=sorted(
                            {evidence.document_id for evidence in case.gold_evidence}
                        ),
                        document_recall=document_recall,
                        evidence_recall=evidence_recall,
                        retrieved=outcome.chunks,
                        model_call_attempts=outcome.model_call_attempts,
                        model_cache_hits=outcome.model_cache_hits,
                    )
                    output.write(record.model_dump_json(exclude_defaults=True) + "\n")
                    output.flush()
                    records.append(record)
                    completed_ids.add(case.id)
        finally:
            if runtime is not None:
                await runtime.close()

        pending_count = len(target_cases) - len(completed_ids)
        status = "completed" if pending_count == 0 else "partial"

        summary = _summarize_results(records, self.config.mode)
        summary.update(
            {
                "status": status,
                "target_case_count": len(target_cases),
                "completed_case_count": len(completed_ids),
                "pending_case_count": pending_count,
                "skipped_unanswerable_count": sum(
                    case.question_type == QuestionType.UNANSWERABLE
                    for case in self.cases
                ),
                "model_call_attempts": controller.total_attempts if controller else 0,
                "stopped_by_model_call_limit": stopped_by_limit,
                "results_path": str(self.results_path),
                "workspace_dir": str(self.config.workspace_dir),
            }
        )
        self.summary_path.write_text(
            json.dumps(summary, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return {**summary, "summary_path": str(self.summary_path)}

    def _select_cases(self) -> list[BenchmarkCase]:
        selected_ids = set(self.config.case_ids)
        if selected_ids:
            known_ids = {case.id for case in self.cases}
            if missing_ids := selected_ids.difference(known_ids):
                raise ValueError(f"unknown benchmark case ids: {sorted(missing_ids)}")
        return [
            case
            for case in self.cases
            if case.question_type != QuestionType.UNANSWERABLE
            and (not selected_ids or case.id in selected_ids)
        ]

    def _load_records(self) -> list[RetrievalRecord]:
        if not self.config.resume or not self.results_path.is_file():
            return []
        with self.results_path.open("r", encoding="utf-8") as handle:
            return [RetrievalRecord.model_validate_json(line) for line in handle]

    def _create_model_controller(self) -> ModelCallController | None:
        if self.config.mode == BenchmarkSearchMode.FAST:
            return None
        return ModelCallController(
            ledger_path=self.ledger_path,
            requests_per_minute=self.config.requests_per_minute,
            max_calls_total=self.config.max_model_calls_total,
            max_attempts=self.config.max_attempts,
            retry_base_seconds=self.config.retry_base_seconds,
        )


async def run_recall(config_path: Path) -> dict[str, Any]:
    """Run one in-process TadaAsk recall benchmark batch."""
    logger.remove()
    logger.add(sys.stderr, level="WARNING")
    config = load_recall_config(config_path)
    if int(config.search_options.get("top_k", 8)) < max(RECALL_K):
        raise ValueError("search.top_k must be at least 5 for Recall@5")
    if config.mode != BenchmarkSearchMode.FAST:
        missing = {"provider", "model"}.difference(config.query_expansion)
        if missing:
            raise ValueError(
                "query_expansion.provider and query_expansion.model are required "
                "for adaptive/full recall"
            )
        base_url = config.query_expansion.get("base_url", "")
        if "PORT" in base_url.upper():
            raise ValueError("query_expansion.base_url still contains a placeholder")
        if config.query_expansion["provider"] != "ollama":
            api_key_env = config.query_expansion.get("api_key_env")
            if not api_key_env or not re.fullmatch(
                r"[A-Za-z_][A-Za-z0-9_]*", api_key_env
            ):
                raise ValueError(
                    "query_expansion.api_key_env must name an environment variable"
                )
            if not os.environ.get(api_key_env):
                raise ValueError(
                    "the API key environment variable configured by "
                    "query_expansion.api_key_env is not available"
                )

    from .tadaask import TadaAskRuntime

    cases = load_jsonl(config.bundle_dir / "cases.jsonl", BenchmarkCase)
    documents = load_jsonl(config.bundle_dir / "documents.jsonl", BenchmarkDocument)
    runner = RecallRunner(
        config=config,
        cases=cases,
        documents=documents,
        runtime_factory=TadaAskRuntime.create,
    )
    return await runner.run()
