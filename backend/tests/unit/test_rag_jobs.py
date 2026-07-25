import asyncio

import pytest

from app.api.schemas import RAGSyncEvent
from app.core.constants import IngestStage, RAGJobStatus, RAGJobType, RAGSyncEventType
from app.services.jobs.rag_job_manager import RAGJobManager


def event(source_uid: str, message: str) -> RAGSyncEvent:
    return RAGSyncEvent(
        event=RAGSyncEventType.SYNC_PROGRESS,
        source_uid=source_uid,
        ingest_stage=IngestStage.LOADING,
        message=message,
    )


@pytest.mark.asyncio
async def test_job_group_is_mutually_exclusive_and_releases_after_completion() -> None:
    manager = RAGJobManager()
    release = asyncio.Event()

    async def blocking_runner(job):
        yield event(job.source_uid, "started")
        await release.wait()

    first = await manager.start_job(
        job_type=RAGJobType.INDEXING,
        source_uid="source",
        active_group="source:source",
        runner=blocking_runner,
    )
    second = await manager.start_job(
        job_type=RAGJobType.WEB_CRAWL_SYNC,
        source_uid="source",
        active_group="source:source",
        runner=blocking_runner,
    )

    assert second is first
    release.set()
    await first.task
    assert first.status == RAGJobStatus.COMPLETED

    third = await manager.start_job(
        job_type=RAGJobType.INDEXING,
        source_uid="source",
        active_group="source:source",
        runner=blocking_runner,
    )
    assert third is not first
    await manager.shutdown()


@pytest.mark.asyncio
async def test_job_replays_sequences_to_subscribers_and_records_failures() -> None:
    manager = RAGJobManager()

    async def successful_runner(job):
        yield event(job.source_uid, "one")
        yield event(job.source_uid, "two")

    job = await manager.start_job(
        job_type=RAGJobType.INDEXING,
        source_uid="source",
        runner=successful_runner,
    )
    await job.task
    replayed = [stored async for stored in manager.subscribe(job_uid=job.job_uid, after_sequence=1)]

    assert job.status == RAGJobStatus.COMPLETED
    assert [stored.sequence for stored in replayed] == [2]
    assert replayed[0].event.message == "two"

    async def failing_runner(job):
        yield event(job.source_uid, "before failure")
        raise RuntimeError("broken pipeline")

    failed = await manager.start_job(
        job_type=RAGJobType.INDEXING,
        source_uid="failed-source",
        runner=failing_runner,
    )
    await failed.task

    assert failed.status == RAGJobStatus.FAILED
    assert failed.error == "broken pipeline"
    assert [stored.sequence for stored in failed.events] == [1, 2]
    assert failed.events[-1].event.event == RAGSyncEventType.SYNC_FAILED


@pytest.mark.asyncio
async def test_shutdown_cancels_active_jobs_without_leaving_them_running() -> None:
    manager = RAGJobManager()
    started = asyncio.Event()

    async def endless_runner(job):
        started.set()
        yield event(job.source_uid, "started")
        await asyncio.Event().wait()

    job = await manager.start_job(
        job_type=RAGJobType.INDEXING,
        source_uid="source",
        runner=endless_runner,
    )
    await started.wait()
    await manager.shutdown()

    assert job.status == RAGJobStatus.CANCELLED
    assert manager.list_active_jobs() == []
