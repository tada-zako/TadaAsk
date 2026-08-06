from pathlib import Path
from typing import Any

import pytest

from app.rag.query_expand import ExpandedQuery, QueryExpander
from benchmarks.rag.runner import BenchmarkSearchMode, ModelCallController
from benchmarks.rag.runner.tadaask import _ControlledCompleter


class FakeAppCompleter:
    model_name = "fake-model"
    provider_name = "fake-provider"

    def __init__(self) -> None:
        self.call_count = 0

    async def complete_structured(
        self,
        *,
        messages: list[Any],
        model_settings: Any,
        schema: type[ExpandedQuery],
    ) -> ExpandedQuery:
        self.call_count += 1
        return schema(
            keywords=["cache"],
            alternative_queries=["persistent cache"],
            hypothetical_document="The response is checkpointed.",
        )


@pytest.mark.asyncio
async def test_query_expander_uses_controlled_completer_and_persistent_cache(
    tmp_path: Path,
) -> None:
    ledger_path = tmp_path / "model-calls.jsonl"
    delegate = FakeAppCompleter()
    controller = ModelCallController(
        ledger_path=ledger_path,
        requests_per_minute=60000,
        max_calls_per_batch=2,
        max_calls_total=2,
        max_attempts=1,
        retry_base_seconds=0,
    )
    controller.begin_case("case-1", BenchmarkSearchMode.ADAPTIVE)
    first = await QueryExpander(cache_enabled=False).expand_query(
        "How is the response cached?",
        completer=_ControlledCompleter(delegate, controller),
    )
    assert first.keywords == ["cache"]
    assert delegate.call_count == 1
    assert controller.finish_case() == (1, 0)

    resumed_delegate = FakeAppCompleter()
    resumed_controller = ModelCallController(
        ledger_path=ledger_path,
        requests_per_minute=60000,
        max_calls_per_batch=2,
        max_calls_total=2,
        max_attempts=1,
        retry_base_seconds=0,
    )
    resumed_controller.begin_case("case-2", BenchmarkSearchMode.ADAPTIVE)
    second = await QueryExpander(cache_enabled=False).expand_query(
        "How is the response cached?",
        completer=_ControlledCompleter(resumed_delegate, resumed_controller),
    )
    assert second == first
    assert resumed_delegate.call_count == 0
    assert resumed_controller.finish_case() == (0, 1)
