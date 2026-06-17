import asyncio
from typing import AsyncIterable, Callable, TypeVar

from loguru import logger

from app.api.schemas import IngestProgressEvent


T = TypeVar("T")

# 泛型处理器定义
WorkProcessor = Callable[[T], AsyncIterable[IngestProgressEvent]]
ErrorHandler = Callable[[T, Exception], AsyncIterable[IngestProgressEvent]]


class IngestRunService:
    """文档 ingest 操作的执行器；负责并发控制、事件包装、错误处理等流程"""

    async def run_many_ingest(
        self,
        *,
        items: list[T],
        processor: WorkProcessor[T],
        max_concurrency: int,
        start_event: IngestProgressEvent,
        complete_event: IngestProgressEvent,
        on_error: ErrorHandler[T] | None = None,
    ) -> AsyncIterable[IngestProgressEvent]:
        """处理多个文档的通用流程，负责并发控制、事件包装和错误处理"""
        async for event in self._run(
            item_stream=self._iter_item(items),
            processor=processor,
            max_concurrency=max_concurrency,
            start_event=start_event,
            complete_event=complete_event,
            on_error=on_error,
        ):
            yield event

    async def run_stream_ingest(
        self,
        *,
        item_stream: AsyncIterable[T],
        processor: WorkProcessor[T],
        max_concurrency: int,
        start_event: IngestProgressEvent,
        complete_event: IngestProgressEvent,
        on_error: ErrorHandler[T] | None = None,
    ) -> AsyncIterable[IngestProgressEvent]:
        """处理流式文档的通用流程，负责并发控制、事件包装和错误处理"""
        async for event in self._run(
            item_stream=item_stream,
            processor=processor,
            max_concurrency=max_concurrency,
            start_event=start_event,
            complete_event=complete_event,
            on_error=on_error,
        ):
            yield event

    async def _iter_item(self, items: list[T]) -> AsyncIterable[T]:
        """异步迭代"""
        for item in items:
            yield item

    async def _run(
        self,
        *,
        item_stream: AsyncIterable[T],
        processor: WorkProcessor[T],
        max_concurrency: int,
        start_event: IngestProgressEvent,
        complete_event: IngestProgressEvent,
        on_error: ErrorHandler[T] | None,
    ) -> AsyncIterable[IngestProgressEvent]:
        """核心执行逻辑：并发处理、事件包装、错误处理"""

        # 异步并发相关变量设置
        queue: asyncio.Queue[IngestProgressEvent] = asyncio.Queue()
        semaphore = asyncio.Semaphore(max_concurrency)

        producer_done = False  # 生产全部完成
        running_tasks: set[asyncio.Task[None]] = set()

        # 发送开始事件
        yield start_event

        async def worker(item: T) -> None:
            """单个文档处理 worker"""
            try:
                async for event in processor(item):
                    await queue.put(event)
            except Exception as exc:
                logger.exception(f"Error processing item: {exc}")
                if on_error:
                    async for event in on_error(item, exc):
                        await queue.put(event)
                else:
                    raise
            finally:
                # !important 手动释放信号量
                semaphore.release()

        async def producer() -> None:
            """生产者：从 item_stream 中读取并启动 worker"""
            nonlocal producer_done

            try:
                async for item in item_stream:
                    # !important 并发控制；限制任务创建速率
                    await semaphore.acquire()

                    task = asyncio.create_task(worker(item))
                    running_tasks.add(task)
                    task.add_done_callback(
                        running_tasks.discard
                    )  # 任务完成后从集合中移除
            finally:
                # 防止 item_stream 异常；确保 producer_done 状态正确更新
                producer_done = True

        # 启动生产者
        producer_task = asyncio.create_task(producer())

        try:
            # 监听生产状态
            while not producer_done or running_tasks:
                try:
                    # 等待 event，防止死锁：
                    # 当 producer 完成并且 running_tasks 为空时，
                    # 如果代码还在等待 queue.get()，就会死锁；
                    event = await asyncio.wait_for(queue.get(), timeout=0.1)
                    yield event
                except asyncio.TimeoutError:
                    continue
        finally:
            # 如果 yield event 阶段发生异常（例如前端关闭连接）
            # 这里需要确保所有后台任务能够正确结束，防止资源泄漏
            # 强制取消生产者
            if not producer_task.done():
                producer_task.cancel()

            # 强制取消剩余的 worker 任务
            for task in list(running_tasks):
                if not task.done():
                    task.cancel()

            # 等待任务彻底退出，释放资源
            await asyncio.gather(producer_task, *running_tasks, return_exceptions=True)

        # 发送完成事件
        yield complete_event
