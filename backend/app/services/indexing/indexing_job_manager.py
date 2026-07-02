import uuid
import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import AsyncIterator

from .source_item_indexing import SourceItemIndexingService

from app.core.constants import IndexingJobStatus, RAGSyncEventType, IngestStage
from app.api.schemas import RAGSyncEvent


@dataclass
class StoredIndexingEvent:
    """
    暂存的 index 任务事件；
    index pipeline 事件流 yield 的 event 暂存类型，
    便于 SSE 请求查看 indexing job 进度时，获取之前的事件
    """

    sequence: int  # 事件序号
    event: RAGSyncEvent
    created_at: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )  # 事件创建时间


@dataclass
class IndexingJob:
    """
    文档 index 任务对象；
    保存整条 index pipeline 的关键信息，
    是实际 index job 任务处理的对象
    """

    job_uid: str
    source_uid: str
    source_item_uids: list[str]
    status: IndexingJobStatus = IndexingJobStatus.QUEUED
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None  # job 开始进入 RUNNING 状态时间
    finished_at: datetime | None = None
    error: str | None = None  # job 执行失败时的错误信息
    task: asyncio.Task | None = (
        None  # index job 本身作为 asyncio.Task 在后台运行，IndexingJob 对象需要持有该任务
    )
    next_event_sequence: int = 1  # 下一个事件序号
    events: deque[StoredIndexingEvent] = field(
        default_factory=lambda: deque(maxlen=500)
    )  # 暂存的 index 事件；最高上限为 500 条，超过则丢弃最早的事件
    subscribers: set[asyncio.Queue[StoredIndexingEvent | None]] = field(
        default_factory=set
    )  # SSE 订阅者集合；index pipeline 事件流 yield 的 event 通过 asyncio.Queue 推送给对应的 SSE 订阅者


class IndexingJobManager:
    """
    文档 index 任务管理器
    """

    def __init__(self, indexing_service: SourceItemIndexingService):
        self.indexing_service = indexing_service
        self._jobs: dict[str, IndexingJob] = {}  # job_uid -> IndexingJob
        self._active_by_source: dict[
            str, str
        ] = {}  # source_uid -> job_uid; 便于前端基于 source_uid 查询对应的 active job
        self._lock = asyncio.Lock()  # 管理 jobs 的并发锁

    async def start_job(
        self, *, source_uid: str, source_item_uids: list[str]
    ) -> IndexingJob:
        """启动 index job"""

        async with self._lock:
            # 持有锁，确保同一 source_uid 只有一个 active job

            active_job_uid = self._active_by_source.get(source_uid)
            if active_job_uid:
                # 如果 source 以及有对应的 active job
                active_job = self._jobs.get(active_job_uid)
                if active_job and active_job.status in (
                    IndexingJobStatus.QUEUED,
                    IndexingJobStatus.RUNNING,
                ):
                    # 如果 active job 仍然处于 QUEUED 或 RUNNING 状态，直接返回该 active job
                    return active_job

            # 创建新的 index job 对象
            job = IndexingJob(
                job_uid=f"idx_{uuid.uuid4().hex}",
                source_uid=source_uid,
                source_item_uids=source_item_uids,
            )
            self._jobs[job.job_uid] = job
            self._active_by_source[source_uid] = job.job_uid
            job.task = asyncio.create_task(self._run_job(job))
            return job

    def get_job(self, job_uid: str) -> IndexingJob | None:
        """获取指定 job_uid 的 index job 对象"""
        return self._jobs.get(job_uid)

    async def subscribe(
        self, *, job_uid: str, after_sequence: int = 0
    ) -> AsyncIterator[StoredIndexingEvent]:
        """添加 SSE 订阅者，并持续输出 index 事件"""
        job = self.get_job(job_uid)
        if not job:
            raise ValueError("Indexing job not found")

        # 创建订阅队列
        queue: asyncio.Queue[StoredIndexingEvent | None] = asyncio.Queue(maxsize=100)
        job.subscribers.add(queue)

        try:
            # 补发缓存事件
            for stored in list(job.events):
                if stored.sequence > after_sequence:
                    yield stored

            if job.status in (
                IndexingJobStatus.COMPLETED,
                IndexingJobStatus.FAILED,
                IndexingJobStatus.CANCELLED,
            ):
                # job 已经结束
                return

            while True:
                # 持续输出事件
                stored = await queue.get()
                if stored is None:
                    # 订阅者队列收到 None，表示 job 已结束
                    return
                yield stored
        finally:
            # 移除订阅者队列
            job.subscribers.discard(queue)

    def get_active_job_by_source(self, source_uid: str) -> IndexingJob | None:
        """获取指定 source_uid 的 active job"""
        active_job_uid = self._active_by_source.get(source_uid)
        if not active_job_uid:
            return None

        # 检查 job 是否有效；由于不持有锁，可能在此期间 job 已经完成或被取消
        job = self._jobs.get(active_job_uid)
        if not job:
            self._active_by_source.pop(source_uid, None)
            return None

        if job.status not in (IndexingJobStatus.QUEUED, IndexingJobStatus.RUNNING):
            # 检查 job 状态
            self._active_by_source.pop(source_uid, None)
            return None

        return job

    async def _run_job(self, job: IndexingJob) -> None:
        """执行 index job"""
        job.status = IndexingJobStatus.RUNNING
        job.started_at = datetime.now(UTC)

        try:
            async for event in self.indexing_service.ingest_source_items(
                source_uid=job.source_uid, source_item_uids=job.source_item_uids
            ):
                # 广播事件
                await self._emit(job, event)

            # job 执行完成
            job.status = IndexingJobStatus.COMPLETED

        except asyncio.CancelledError:
            # job 被取消
            job.status = IndexingJobStatus.CANCELLED
            raise

        except Exception as exc:
            # job 出现异常
            job.status = IndexingJobStatus.FAILED
            job.error = str(exc)
            await self._emit(
                job,
                RAGSyncEvent(
                    event=RAGSyncEventType.SYNC_FAILED,
                    source_uid=job.source_uid,
                    ingest_stage=IngestStage.FAILED,
                    message="Document indexing job failed",
                    error=str(exc),
                ),
            )
        finally:
            # 最后处理 job 状态
            job.finished_at = datetime.now(UTC)
            self._active_by_source.pop(job.source_uid, None)  # 移除 active job 映射
            for queue in list(job.subscribers):
                # 通知所有订阅者 job 已完成，发送 None 作为结束信号
                await queue.put(None)

    async def _emit(self, job: IndexingJob, event: RAGSyncEvent) -> None:
        """广播事件给所有订阅者"""
        stored_event = StoredIndexingEvent(
            sequence=job.next_event_sequence, event=event
        )
        job.events.append(stored_event)
        job.next_event_sequence += 1  # 增加事件序号

        # 广播事件
        for queue in list(job.subscribers):
            try:
                # 不进行队列等待，立即插入
                queue.put_nowait(stored_event)
            except asyncio.QueueFull:
                # 订阅者队列已满，静默丢弃事件
                job.subscribers.discard(queue)
