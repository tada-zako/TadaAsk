from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.constants import SearchMode
from benchmarks.rag.dataset import validate_bundle
from benchmarks.rag.schemas import (
    BenchmarkCase,
    BenchmarkRunResult,
    JudgeResult,
    JudgeScores,
    JudgeVerdict,
    QuestionType,
    RunStage,
    RunStatus,
)


BENCHMARK_ROOT = Path(__file__).parents[2] / "benchmarks" / "rag"


def test_smoke_bundle_validates_and_returns_counts_only() -> None:
    summary = validate_bundle(BENCHMARK_ROOT / "configs" / "smoke.json")

    assert summary.case_count == 10
    assert summary.document_count == 8
    assert summary.answerable_count == 9
    assert summary.unanswerable_count == 1
    assert summary.cases_by_language == {"en": 4, "mixed": 1, "zh": 5}
    assert summary.cases_by_question_type == {
        "direct": 3,
        "exact": 2,
        "multi_document": 1,
        "multi_turn": 1,
        "paraphrase": 2,
        "unanswerable": 1,
    }


def test_unanswerable_case_rejects_answer_payload() -> None:
    with pytest.raises(ValidationError):
        BenchmarkCase(
            id="invalid.unanswerable",
            dataset="test",
            dataset_split="test",
            language="zh",
            question_type=QuestionType.UNANSWERABLE,
            question="没有答案的问题",
            is_answerable=False,
            expected_answer="不应存在",
        )


def test_run_and_judge_results_round_trip() -> None:
    now = datetime.now(tz=timezone.utc)
    run_result = BenchmarkRunResult(
        run_id="run-smoke",
        case_id="smoke.en.direct.tadaask_sources",
        stage=RunStage.END_TO_END,
        requested_mode=SearchMode.FAST,
        actual_mode=SearchMode.FAST,
        status=RunStatus.COMPLETED,
        started_at=now,
        completed_at=now,
        answer="Local files and crawled web pages.",
        latency_ms={"total": 12.5},
    )
    judge_result = JudgeResult(
        run_id=run_result.run_id,
        case_id=run_result.case_id,
        mode=run_result.requested_mode,
        judge_model_profile_uid="model-judge",
        scores=JudgeScores(correctness=4, faithfulness=4, relevance=4),
        verdict=JudgeVerdict.PASS,
        reasons=["The answer matches the expected evidence."],
        created_at=now,
    )

    assert (
        BenchmarkRunResult.model_validate_json(run_result.model_dump_json())
        == run_result
    )
    assert (
        JudgeResult.model_validate_json(judge_result.model_dump_json()) == judge_result
    )
