import asyncio
import time
import uuid
from collections import deque
from collections.abc import AsyncIterable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from loguru import logger

from app.api.schemas import RAGSyncEvent
from app.core.constants import IngestStage, RAGJobStatus, RAGJobType, RAGSyncEventType

# RAG job 后台运行对象类型；
# RAGJobManager 调用者需要确保将内部的实际运行对象封装成该类型的函数
type RAGJobRunner = Callable[["RAGJob"], AsyncIterable[RAGSyncEvent]]


@dataclass
class StoredRAGJobEvent:
    """
    RAG job 事件缓存项;
    pipeline 事件流 yield 的 event 暂存类型，
    便于 SSE 请求查看 job 进度时，获取之前的事件
    """

    sequence: int
    event: RAGSyncEvent
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class RAGJob:
    """RAG 后台任务对象"""

    job_uid: str
    job_type: RAGJobType
    source_uid: str
    source_item_uids: list[str] = field(default_factory=list)
    status: RAGJobStatus = RAGJobStatus.QUEUED
    active_group: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None  # job 开始进入 RUNNING 状态时间
    finished_at: datetime | None = None
    error: str | None = None
    task: asyncio.Task | None = (
        None  # index job 本身作为 asyncio.Task 在后台运行，IndexingJob 对象需要持有该任务
    )
    next_event_sequence: int = 1
    events: deque[StoredRAGJobEvent] = field(
        default_factory=lambda: deque(maxlen=500)
    )  # 暂存的 index 事件；最高上限为 500 条，超过则丢弃最早的事件
    subscribers: set[asyncio.Queue[StoredRAGJobEvent | None]] = field(
        default_factory=set
    )  # SSE 订阅者集合；index pipeline 事件流 yield 的 event 通过 asyncio.Queue 推送给对应的 SSE 订阅者


class RAGJobManager:
    """轻量级进程内 RAG 后台任务管理器"""

    def __init__(self):
        self._jobs: dict[str, RAGJob] = {}
        self._active_by_group: dict[
            str, str
        ] = {}  # group_key -> job_uid; 便于前端基于 group_key 查询对应的 active job
        self._lock = asyncio.Lock()

    async def start_job(
        self,
        *,
        job_type: RAGJobType,
        source_uid: str,
        runner: RAGJobRunner,
        source_item_uids: list[str] | None = None,
        active_group: str | None = None,
    ) -> RAGJob:
        """创建并启动后台 job；
        相同 active_group 的运行中 job 会被复用"""
        async with self._lock:
            # 持有锁，确保同一 source_uid 只有一个 active job

            if active_group:
                # 检查是否已经有对应的 active job
                active_job_uid = self._active_by_group.get(active_group)
                active_job = self._jobs.get(active_job_uid) if active_job_uid else None
                if active_job and active_job.status in (
                    RAGJobStatus.QUEUED,
                    RAGJobStatus.RUNNING,
                ):
                    # 目标 job 已经存在并且处于运行中
                    logger.bind(
                        event="rag.job.reused",
                        job_uid=active_job.job_uid,
                        job_type=active_job.job_type.value,
                        source_uid=active_job.source_uid,
                        source_item_count=len(active_job.source_item_uids),
                    ).info("Active RAG job reused")
                    return active_job

            # 创建新的 job 对象
            job = RAGJob(
                job_uid=f"rag_{uuid.uuid4().hex}",
                job_type=job_type,
                source_uid=source_uid,
                source_item_uids=list(source_item_uids or []),
                active_group=active_group,
            )
            self._jobs[job.job_uid] = job
            if active_group:
                self._active_by_group[active_group] = job.job_uid

            job.task = asyncio.create_task(self._run_job(job=job, runner=runner))
            logger.bind(
                event="rag.job.queued",
                job_uid=job.job_uid,
                job_type=job.job_type.value,
                source_uid=job.source_uid,
                source_item_count=len(job.source_item_uids),
            ).info("RAG job queued")
            return job

    def get_job(self, job_uid: str) -> RAGJob | None:
        """获取指定 job。"""
        return self._jobs.get(job_uid)

    def list_active_jobs(self) -> list[RAGJob]:
        """列出所有仍在运行中的 job。"""
        return [
            job
            for job in self._jobs.values()
            if job.status in (RAGJobStatus.QUEUED, RAGJobStatus.RUNNING)
        ]

    async def subscribe(
        self, *, job_uid: str, after_sequence: int = 0
    ) -> AsyncIterable[StoredRAGJobEvent]:
        """订阅 job 事件；
        先补发缓存，再持续监听新事件"""

        # 创建订阅队列
        queue: asyncio.Queue[StoredRAGJobEvent | None] = asyncio.Queue(maxsize=100)

        async with self._lock:
            job = self._jobs.get(job_uid)
            if not job:
                raise ValueError("RAG job not found")

            job.subscribers.add(queue)

            # 获取缓存事件
            cached_events = [
                stored
                for stored in list(job.events)
                if stored.sequence > after_sequence
            ]
            is_finished = job.status in (
                RAGJobStatus.COMPLETED,
                RAGJobStatus.FAILED,
                RAGJobStatus.CANCELLED,
            )

        try:
            for stored in cached_events:
                # 补发旧事件
                yield stored

            if is_finished:
                return

            while True:
                # 持续输出事件
                stored = await queue.get()
                if stored is None:
                    return
                yield stored
        finally:
            async with self._lock:
                # 移除订阅者队列
                job = self._jobs.get(job_uid)
                if job:
                    job.subscribers.discard(queue)

    async def shutdown(self) -> None:
        """应用关闭时取消仍在运行的后台任务。"""
        async with self._lock:
            tasks = [
                job.task
                for job in self._jobs.values()
                if job.task
                and job.status in (RAGJobStatus.QUEUED, RAGJobStatus.RUNNING)
            ]

        for task in tasks:
            # 强行关闭所有任务
            if not task.done():
                task.cancel()

        if tasks:
            # 确认无孤儿任务
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _run_job(self, *, job: RAGJob, runner: RAGJobRunner) -> None:
        """后台消费业务 runner 事件，并广播给 SSE 订阅者。"""
        started_at = time.perf_counter()
        job_log = logger.bind(
            job_uid=job.job_uid,
            job_type=job.job_type.value,
            source_uid=job.source_uid,
            source_item_count=len(job.source_item_uids),
        )
        job.status = RAGJobStatus.RUNNING
        job.started_at = datetime.now(UTC)
        job_log.bind(event="rag.job.started").info("RAG job started")

        try:
            async for event in runner(job):
                # 广播事件
                await self._emit(job=job, event=event)

            # job 执行完成
            job.status = RAGJobStatus.COMPLETED
            job_log.bind(
                event="rag.job.completed",
                emitted_event_count=job.next_event_sequence - 1,
                duration_ms=round((time.perf_counter() - started_at) * 1000, 3),
            ).info("RAG job completed")

        except asyncio.CancelledError:
            # job 被取消
            job.status = RAGJobStatus.CANCELLED
            job_log.bind(
                event="rag.job.cancelled",
                emitted_event_count=job.next_event_sequence - 1,
                duration_ms=round((time.perf_counter() - started_at) * 1000, 3),
            ).info("RAG job cancelled")
            raise

        except Exception as exc:
            # job 出现异常
            error_id = uuid.uuid4().hex
            job_log.bind(
                event="rag.job.failed",
                error_id=error_id,
                exception_type=type(exc).__name__,
                emitted_event_count=job.next_event_sequence - 1,
                duration_ms=round((time.perf_counter() - started_at) * 1000, 3),
            ).opt(exception=exc).error("RAG job failed")
            job.status = RAGJobStatus.FAILED
            job.error = str(exc)
            await self._emit(
                job=job,
                event=RAGSyncEvent(
                    event=RAGSyncEventType.SYNC_FAILED,
                    source_uid=job.source_uid,
                    ingest_stage=IngestStage.FAILED,
                    message="RAG job failed",
                    error="RAG job failed",
                    error_id=error_id,
                ),
            )

        finally:
            # 最后处理 job 状态
            job.finished_at = datetime.now(UTC)
            await self._clear_active_group(job)
            await self._notify_job_finished(job)

    async def _emit(self, *, job: RAGJob, event: RAGSyncEvent) -> None:
        """缓存并广播事件。"""
        async with self._lock:
            stored_event = StoredRAGJobEvent(
                sequence=job.next_event_sequence,
                event=event,
            )
            job.events.append(stored_event)
            job.next_event_sequence += 1  # 增加事件序号
            subscribers = list(job.subscribers)  # 订阅者快照

        for queue in subscribers:
            try:
                # 不进行队列等待，立即插入
                queue.put_nowait(stored_event)
            except asyncio.QueueFull:
                async with self._lock:
                    # 订阅者队列已满，静默丢弃事件
                    job.subscribers.discard(queue)

    async def _clear_active_group(self, job: RAGJob) -> None:
        """只清理仍指向当前 job 的 active 映射"""
        if not job.active_group:
            return

        async with self._lock:
            # 启动锁，避免旧 job 误删新 job
            if self._active_by_group.get(job.active_group) == job.job_uid:
                self._active_by_group.pop(job.active_group, None)

    async def _notify_job_finished(self, job: RAGJob) -> None:
        """通知订阅者 job 已结束"""
        async with self._lock:
            # 获取订阅者快照
            subscribers = list(job.subscribers)

        for queue in subscribers:
            self._put_finish_signal(queue)

    def _put_finish_signal(
        self, queue: asyncio.Queue[StoredRAGJobEvent | None]
    ) -> None:
        """尽量保证结束信号能进入订阅队列（best-effort）；
        尽可能让慢 client 接收到结束信号
        """
        try:
            queue.put_nowait(None)
            return
        except asyncio.QueueFull:
            pass

        try:
            # 队列已满，尝试强行取出旧事件，腾出空间
            queue.get_nowait()
        except asyncio.QueueEmpty:
            pass

        try:
            # 再次尝试放入完成信号
            queue.put_nowait(None)
        except asyncio.QueueFull:
            # 订阅者已经严重滞后，后续 finally 会移除该队列。
            return
