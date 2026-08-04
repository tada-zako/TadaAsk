from pathlib import Path

from benchmarks.rag.bundle import audit_bundle


BENCHMARK_ROOT = Path(__file__).parents[1] / "rag"


def test_smoke_bundle_validates_evidence_and_counts() -> None:
    summary = audit_bundle(
        BENCHMARK_ROOT / "resources" / "smoke",
        BENCHMARK_ROOT / "resources" / "configs" / "smoke.json",
    )

    assert summary["case_count"] == 10
    assert summary["document_count"] == 8
    assert summary["answerable_count"] == 9
    assert summary["unanswerable_count"] == 1
    assert summary["cases_by_language"] == {"en": 4, "mixed": 1, "zh": 5}
    assert summary["cases_by_question_type"] == {
        "direct": 3,
        "exact": 2,
        "multi_document": 1,
        "multi_turn": 1,
        "paraphrase": 2,
        "unanswerable": 1,
    }
