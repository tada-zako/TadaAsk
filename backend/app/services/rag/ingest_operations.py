import asyncio
from typing import AsyncIterable, Callable, cast

from loguru import logger

from app.db.models import Source, SourceItem
from app.crud import SourceCRUD
from app.api.schemas import IngestProgressEvent, IngestPausedResponse
from app.core.constants import SourceItemProcessStatus, IngestStage, RAGIngestEventType
from app.core.exceptions import DocumentPausedException


# 单 SourceItem 处理器类型定义
SourceItemProcessor = Callable[[Source, SourceItem], AsyncIterable[IngestProgressEvent]]


class IngestOperationsService:
    """通用 Ingest 操作: 请求暂停 / 可恢复检查 / 暂停检查点 / worker 事件包装"""

    def __init__(
        self,
        *,
        source_crud: SourceCRUD,
    ):
        """具体的参数由依赖注入"""
        self.source_crud = source_crud

    async def request_pause_ingest(
        # NOTE: 这里的 source_item 实例传递之前，需要确保对应 source, status 不是完成/PAUSED
        self,
        source: Source,
        source_item: SourceItem,
    ) -> IngestPausedResponse:
        """请求暂停文档处理"""
        if source_item.status != SourceItemProcessStatus.PROCESSING:
            logger.warning(
                f"SourceItem {source_item.uid} 状态为 {source_item.status}，无法暂停"
            )
            return IngestPausedResponse(
                source_uid=source.uid,
                source_item_uid=source_item.uid,
                process_status=source_item.status,
                message="No running ingest to pause",
            )

        # 更新数据库状态，等待处理流程检查点生效
        await self.source_crud.update_source_item_status(
            source_item, SourceItemProcessStatus.PAUSE_REQUESTED
        )
        logger.info(
            f"SourceItem {source_item.uid} 已标记为 PAUSE_REQUESTED，等待处理流程检查点生效"
        )
        return IngestPausedResponse(
            source_uid=source.uid,
            source_item_uid=source_item.uid,
            process_status=SourceItemProcessStatus.PAUSE_REQUESTED,
            message="Ingest pause requested, waiting for checkpoint",
        )

    async def ensure_resumable(self, *, source_item: SourceItem) -> None:
        """确保文档可恢复"""
        # 仅允许从 PAUSED 状态恢复
        if source_item.status != SourceItemProcessStatus.PAUSED:
            logger.warning(
                f"SourceItem {source_item.uid} 状态为 {source_item.status}，无法恢复"
            )
            raise ValueError(
                f"SourceItem {source_item.uid} is not in PAUSED status, cannot resume"
            )

    async def pause_checkpoint(self, source_item_id: int) -> None:
        """处理流程中的暂停检查点；在关键步骤前调用，检查是否有暂停请求"""
        item = cast(
            SourceItem, await self.source_crud.get_source_item_by_id(source_item_id)
        )  # 内部调用；能够确保结果存在

        if item.status == SourceItemProcessStatus.PAUSE_REQUESTED:
            # 更新状态为 PAUSED，触发暂停事件
            await self.source_crud.update_source_item_status(
                item, SourceItemProcessStatus.PAUSED
            )
            logger.info(f"SourceItem {item.uid} 已更新状态为 PAUSED，触发暂停")
            # 主动触发暂停事件
            raise DocumentPausedException(f"Document {item.uid} paused by user request")

    async def run_ingest(
        self,
        *,
        source: Source,
        source_items: list[SourceItem],
        processor: SourceItemProcessor,
        max_concurrency: int,
    ) -> AsyncIterable[IngestProgressEvent]:
        """处理文档并存储到数据库中"""

        # 异步并发相关
        queue: asyncio.Queue[IngestProgressEvent] = asyncio.Queue()
        # TODO: 并发控制应该提升到更通用的层面，作为有状态服务的一部分；目前先在这里实现一个简单的 Semaphore 控制并发量
        semaphore = asyncio.Semaphore(max_concurrency)

        completed_workers = 0

        # 发送开始事件
        yield IngestProgressEvent(
            event=RAGIngestEventType.INGEST_START,
            source_uid=source.uid,
            ingest_stage=IngestStage.LOADING,
            process_status=SourceItemProcessStatus.PROCESSING,
            item_progress=0.0,
            message="Document ingestion started",
        )

        async def worker(source_item: SourceItem):
            """单个文档处理 worker"""
            async with semaphore:
                try:
                    async for event in processor(source, source_item):
                        await queue.put(event)
                except DocumentPausedException:
                    # 触发暂停事件
                    await queue.put(
                        IngestProgressEvent(
                            event=RAGIngestEventType.ITEM_PAUSED,
                            source_uid=source.uid,
                            source_item_uid=source_item.uid,
                            ingest_stage=IngestStage.PAUSED,
                            process_status=SourceItemProcessStatus.PAUSED,
                            message="Document ingest paused",
                        )
                    )

                except Exception as e:
                    # 异常处理
                    logger.error(f"Error processing document {source_item.uid}: {e}")
                    # 更新数据库状态
                    await self.source_crud.update_source_item_status(
                        source_item, SourceItemProcessStatus.FAILED
                    )
                    await queue.put(
                        IngestProgressEvent(
                            event=RAGIngestEventType.ITEM_FAILED,
                            source_uid=source.uid,
                            source_item_uid=source_item.uid,
                            ingest_stage=IngestStage.FAILED,
                            process_status=SourceItemProcessStatus.FAILED,
                            message="Document ingest failed",
                            error=str(e),
                        )
                    )

                finally:
                    # 最终完成
                    await queue.put(
                        IngestProgressEvent(
                            event=RAGIngestEventType._WORKER_DONE,
                            source_uid=source.uid,
                            source_item_uid=source_item.uid,
                            ingest_stage=IngestStage.COMPLETED,
                            process_status=SourceItemProcessStatus.COMPLETED,
                            message="Document ingest completed",
                            item_progress=1.0,
                        )
                    )

        # 启动任务队列
        tasks = [asyncio.create_task(worker(item)) for item in source_items]

        # 监听事件队列
        while completed_workers < len(source_items):
            event = await queue.get()
            if event.event == RAGIngestEventType._WORKER_DONE:
                completed_workers += 1
                continue  # 内部事件，不发送给前端

            yield event

        await asyncio.gather(*tasks)  # 确保所有任务完成
        yield IngestProgressEvent(
            event=RAGIngestEventType.INGEST_COMPLETE,
            source_uid=source.uid,
            ingest_stage=IngestStage.COMPLETED,
            process_status=SourceItemProcessStatus.COMPLETED,
            message="All documents ingested",
            item_progress=1.0,
        )

    async def complete_item(
        self,
        *,
        source: Source,
        source_item: SourceItem,
        message: str = "Ingest completed",
    ) -> IngestProgressEvent:
        """完成单个文档的处理"""
        # 6. 胜利宣言
        await self.source_crud.update_source_item_status(
            source_item, SourceItemProcessStatus.COMPLETED
        )
        return IngestProgressEvent(
            event=RAGIngestEventType.INGEST_PROGRESS,
            source_uid=source.uid,
            source_item_uid=source_item.uid,
            ingest_stage=IngestStage.COMPLETED,
            process_status=SourceItemProcessStatus.COMPLETED,
            item_progress=1.0,
            message=message,
        )
