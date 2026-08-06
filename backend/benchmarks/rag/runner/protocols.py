from pathlib import Path
from typing import Protocol, Sequence

from pydantic import JsonValue

from ..models import BenchmarkDocument
from .schemas import BenchmarkSearchMode, RetrievalOutcome


class RetrievalRuntime(Protocol):
    """Stable boundary between benchmark orchestration and a RAG application."""

    async def prepare_corpus(
        self,
        *,
        bundle_dir: Path,
        documents: Sequence[BenchmarkDocument],
    ) -> None:
        """Prepare or reuse the application-owned corpus index."""
        ...

    async def retrieve(
        self,
        *,
        case_id: str,
        query: str,
        mode: BenchmarkSearchMode,
        search_options: dict[str, JsonValue],
    ) -> RetrievalOutcome:
        """Run one retrieval request and return application-neutral chunks."""
        ...

    async def close(self) -> None:
        """Release application runtime resources."""
        ...
