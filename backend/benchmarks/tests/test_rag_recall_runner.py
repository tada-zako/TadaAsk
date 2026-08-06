from pathlib import Path

import pytest
from pydantic import BaseModel, JsonValue

from benchmarks.rag.models import (
    BenchmarkCase,
    BenchmarkDocument,
    BenchmarkLanguage,
    DocumentFormat,
    GoldEvidence,
    QuestionType,
)
from benchmarks.rag.runner import (
    BenchmarkSearchMode,
    ModelCallController,
    ModelCallLimitReached,
    RecallRunConfig,
    RetrievalOutcome,
    RetrievedChunk,
)
from benchmarks.rag.runner.recall import RecallRunner, run_recall


class FakeRuntime:
    def __init__(self) -> None:
        self.case_ids: list[str] = []

    async def prepare_corpus(
        self, *, bundle_dir: Path, documents: list[BenchmarkDocument]
    ) -> None:
        return None

    async def retrieve(
        self,
        *,
        case_id: str,
        query: str,
        mode: BenchmarkSearchMode,
        search_options: dict[str, JsonValue],
    ) -> RetrievalOutcome:
        self.case_ids.append(case_id)
        return RetrievalOutcome(
            chunks=[
                RetrievedChunk(
                    rank=1,
                    document_id="doc-1",
                    chunk_id=1,
                    content="controlled evidence",
                )
            ]
        )

    async def close(self) -> None:
        return None


class StructuredResult(BaseModel):
    value: str


class RateLimitError(Exception):
    code = 429


@pytest.mark.asyncio
async def test_recall_runner_batches_resumes_and_rejects_changed_identity(
    tmp_path: Path,
) -> None:
    bundle_dir = tmp_path / "bundle"
    corpus_dir = bundle_dir / "corpus"
    corpus_dir.mkdir(parents=True)
    (corpus_dir / "doc.md").write_text("controlled evidence", encoding="utf-8")
    document = BenchmarkDocument(
        id="doc-1",
        dataset="test",
        title="Document",
        language=BenchmarkLanguage.EN,
        document_format=DocumentFormat.MARKDOWN,
        relative_path="corpus/doc.md",
    )
    cases = [
        BenchmarkCase(
            id=f"case-{index}",
            dataset="test",
            language=BenchmarkLanguage.EN,
            question_type=QuestionType.DIRECT,
            question=f"Question {index}",
            gold_evidence=[
                GoldEvidence(document_id="doc-1", text="controlled evidence")
            ],
        )
        for index in range(2)
    ]
    (bundle_dir / "documents.jsonl").write_text(
        document.model_dump_json() + "\n", encoding="utf-8"
    )
    (bundle_dir / "cases.jsonl").write_text(
        "\n".join(case.model_dump_json() for case in cases) + "\n",
        encoding="utf-8",
    )

    runtimes: list[FakeRuntime] = []

    async def create_runtime(
        config: RecallRunConfig, controller: ModelCallController | None
    ) -> FakeRuntime:
        runtime = FakeRuntime()
        runtimes.append(runtime)
        return runtime

    config = RecallRunConfig(
        bundle_dir=bundle_dir,
        workspace_dir=tmp_path / "workspace",
        run_dir=tmp_path / "run",
        mode=BenchmarkSearchMode.FAST,
        resume=False,
        batch_size=1,
        search_options={"top_k": 5},
    )
    first = await RecallRunner(
        config=config,
        cases=cases,
        documents=[document],
        runtime_factory=create_runtime,
    ).run()
    assert first["status"] == "partial"
    assert first["completed_case_count"] == 1

    resumed_config = config.model_copy(update={"resume": True})
    second = await RecallRunner(
        config=resumed_config,
        cases=cases,
        documents=[document],
        runtime_factory=create_runtime,
    ).run()
    assert second["status"] == "completed"
    assert second["completed_case_count"] == 2
    assert [runtime.case_ids for runtime in runtimes] == [["case-0"], ["case-1"]]

    changed_config = resumed_config.model_copy(update={"search_options": {"top_k": 6}})
    with pytest.raises(ValueError, match="fingerprint changed"):
        await RecallRunner(
            config=changed_config,
            cases=cases,
            documents=[document],
            runtime_factory=create_runtime,
        ).run()


@pytest.mark.asyncio
async def test_model_call_controller_retries_caches_and_enforces_total_limit(
    tmp_path: Path,
) -> None:
    ledger_path = tmp_path / "model-calls.jsonl"
    controller = ModelCallController(
        ledger_path=ledger_path,
        requests_per_minute=60000,
        max_calls_per_batch=2,
        max_calls_total=2,
        max_attempts=2,
        retry_base_seconds=0,
    )
    call_count = 0

    async def invoke() -> StructuredResult:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RateLimitError()
        return StructuredResult(value="ok")

    controller.begin_case("case-1", BenchmarkSearchMode.ADAPTIVE)
    result = await controller.execute(
        request={"query": "one"}, schema=StructuredResult, invoke=invoke
    )
    assert result.value == "ok"
    assert controller.finish_case() == (2, 0)

    resumed = ModelCallController(
        ledger_path=ledger_path,
        requests_per_minute=60000,
        max_calls_per_batch=1,
        max_calls_total=2,
        max_attempts=1,
        retry_base_seconds=0,
    )
    resumed.begin_case("case-2", BenchmarkSearchMode.ADAPTIVE)
    cached = await resumed.execute(
        request={"query": "one"}, schema=StructuredResult, invoke=invoke
    )
    assert cached.value == "ok"
    assert resumed.finish_case() == (0, 1)

    resumed.begin_case("case-3", BenchmarkSearchMode.ADAPTIVE)
    with pytest.raises(ModelCallLimitReached, match="total limit"):
        await resumed.execute(
            request={"query": "two"}, schema=StructuredResult, invoke=invoke
        )


@pytest.mark.asyncio
async def test_adaptive_preflight_rejects_invalid_api_key_environment_name(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "recall.toml"
    config_path.write_text(
        """[benchmark]
bundle_dir = "missing-bundle"
workspace_dir = "workspace"
run_dir = "run"
mode = "adaptive"

[search]
top_k = 5

[query_expansion]
provider = "custom"
model = "model"
base_url = "http://127.0.0.1:8000"
api_key_env = "not-an-env-name"
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="must name an environment variable"):
        await run_recall(config_path)
