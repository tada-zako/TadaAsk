import asyncio
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from .schemas import BenchmarkSearchMode, ModelCallRecord


ResultModel = TypeVar("ResultModel", bound=BaseModel)


class ModelCallLimitReached(RuntimeError):
    """Signal that the configured outbound model-call budget is exhausted."""


class ModelCallController:
    """Persist and control structured model calls made during retrieval."""

    def __init__(
        self,
        *,
        ledger_path: Path,
        requests_per_minute: int,
        max_calls_total: int | None,
        max_attempts: int,
        retry_base_seconds: float,
    ) -> None:
        self._ledger_path = ledger_path
        self._minimum_interval = 60 / requests_per_minute
        self._max_calls_total = max_calls_total
        self._max_attempts = max_attempts
        self._retry_base_seconds = retry_base_seconds
        self._last_call_started_at: float | None = None
        self._total_attempts = 0

        if ledger_path.is_file():
            for record in self._read_ledger(ledger_path):
                if record.status == "started":
                    self._total_attempts += 1

    @staticmethod
    def _read_ledger(path: Path) -> list[ModelCallRecord]:
        """Load the small model-call ledger used for resume accounting."""
        with path.open("r", encoding="utf-8") as handle:
            return [ModelCallRecord.model_validate_json(line) for line in handle]

    @property
    def total_attempts(self) -> int:
        """Return all outbound attempts recorded for this run directory."""
        return self._total_attempts

    async def execute(
        self,
        *,
        case_id: str,
        mode: BenchmarkSearchMode,
        invoke: Callable[[], Awaitable[ResultModel]],
    ) -> ResultModel:
        """Perform one rate-limited structured call with bounded retries.

        Args:
            case_id: Benchmark case responsible for the outbound call.
            mode: Retrieval mode used by the case.
            invoke: Existing provider operation supplied by the App adapter.

        Returns:
            A response validated through the original App schema.

        Raises:
            ModelCallLimitReached: The total attempt cap is met.
        """
        for attempt in range(1, self._max_attempts + 1):
            self._check_limits()
            await self._pace()

            self._total_attempts += 1
            self._append(
                ModelCallRecord(
                    case_id=case_id,
                    mode=mode,
                    attempt=attempt,
                    status="started",
                    timestamp=datetime.now(UTC),
                )
            )

            try:
                result = await invoke()
            except Exception as exc:
                self._append(
                    ModelCallRecord(
                        case_id=case_id,
                        mode=mode,
                        attempt=attempt,
                        status="failed",
                        timestamp=datetime.now(UTC),
                        error=self._error_label(exc),
                    )
                )
                if attempt == self._max_attempts or not self._is_retryable(exc):
                    raise
                await asyncio.sleep(self._retry_base_seconds * (2 ** (attempt - 1)))
                continue

            self._append(
                ModelCallRecord(
                    case_id=case_id,
                    mode=mode,
                    attempt=attempt,
                    status="succeeded",
                    timestamp=datetime.now(UTC),
                )
            )
            return result

        raise RuntimeError("model call retry loop exited unexpectedly")

    def _check_limits(self) -> None:
        if (
            self._max_calls_total is not None
            and self._total_attempts >= self._max_calls_total
        ):
            raise ModelCallLimitReached("model-call total limit reached")

    async def _pace(self) -> None:
        if self._last_call_started_at is not None:
            remaining = self._minimum_interval - (
                time.monotonic() - self._last_call_started_at
            )
            if remaining > 0:
                await asyncio.sleep(remaining)
        self._last_call_started_at = time.monotonic()

    def _append(self, record: ModelCallRecord) -> None:
        self._ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with self._ledger_path.open("a", encoding="utf-8", newline="\n") as output:
            output.write(record.model_dump_json(exclude_none=True) + "\n")

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        if isinstance(exc, TimeoutError):
            return True
        status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
        if status is None and (response := getattr(exc, "response", None)) is not None:
            status = getattr(response, "status_code", None)
        try:
            status_code = int(status)
        except (TypeError, ValueError):
            return False
        return status_code == 429 or status_code >= 500

    @staticmethod
    def _error_label(exc: Exception) -> str:
        status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
        return f"{type(exc).__name__}:{status}" if status else type(exc).__name__
