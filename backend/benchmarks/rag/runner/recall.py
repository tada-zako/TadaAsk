import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

from ..bundle import load_jsonl
from ..models import BenchmarkCase, BenchmarkDocument, QuestionType
from .config import load_recall_config
from .results import (
    append_checkpoint,
    load_checkpoints,
    score_retrieval,
    summarize_records,
    write_summary,
)
from .schemas import RecallRunConfig, RetrievalRecord
from .tadaask import RetrievalLimitReached

if TYPE_CHECKING:
    from .tadaask import TadaAskRuntime


class RecallRunner:
    """Run deterministic recall batches against an injected RAG runtime."""

    def __init__(
        self,
        *,
        config: RecallRunConfig,
        cases: list[BenchmarkCase],
        documents: list[BenchmarkDocument],
        runtime: "TadaAskRuntime",
    ) -> None:
        self.config = config
        self.cases = cases
        self.documents = documents
        self.runtime = runtime
        self.results_path = config.run_dir / "recall.jsonl"
        self.summary_path = config.run_dir / "recall-summary.json"

    async def run(self) -> dict[str, Any]:
        """Execute one recoverable batch and write aggregate run state."""
        self.config.run_dir.mkdir(parents=True, exist_ok=True)
        if not self.config.resume:
            for path in (
                self.results_path,
                self.config.run_dir / "model-calls.jsonl",
                self.summary_path,
            ):
                path.unlink(missing_ok=True)

        target_cases = self._select_cases()
        records = load_checkpoints(self.results_path, resume=self.config.resume)
        completed_ids = {
            record.case_id for record in records if record.mode == self.config.mode
        }
        pending_cases = [case for case in target_cases if case.id not in completed_ids]
        stopped_by_limit = False
        if pending_cases:
            await self.runtime.prepare_corpus(
                bundle_dir=self.config.bundle_dir,
                documents=self.documents,
            )

        for case in pending_cases:
            try:
                outcome = await self.runtime.retrieve(
                    case_id=case.id,
                    query=case.expected_standalone_query or case.question,
                )
            except RetrievalLimitReached:
                stopped_by_limit = True
                break

            document_recall, evidence_recall = score_retrieval(
                case=case,
                chunks=outcome.chunks,
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
            append_checkpoint(self.results_path, record)
            records.append(record)
            completed_ids.add(case.id)

        pending_count = len(target_cases) - len(completed_ids)
        status = "completed" if pending_count == 0 else "partial"

        summary = summarize_records(records, self.config.mode)
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
                "model_call_attempts": self.runtime.model_call_attempts,
                "stopped_by_model_call_limit": stopped_by_limit,
                "results_path": str(self.results_path),
                "workspace_dir": str(self.config.workspace_dir),
            }
        )
        write_summary(self.summary_path, summary)
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


async def run_recall(config_path: Path) -> dict[str, Any]:
    """Run one in-process TadaAsk recall benchmark batch."""
    logger.remove()
    logger.add(sys.stderr, level="WARNING")
    config = load_recall_config(config_path)

    from .tadaask import TadaAskRuntime

    cases = load_jsonl(config.bundle_dir / "cases.jsonl", BenchmarkCase)
    documents = load_jsonl(config.bundle_dir / "documents.jsonl", BenchmarkDocument)
    runtime = await TadaAskRuntime.create(config)
    try:
        return await RecallRunner(
            config=config,
            cases=cases,
            documents=documents,
            runtime=runtime,
        ).run()
    finally:
        await runtime.close()
