from typing import cast

from loguru import logger

from app.db.models import Source, SourceItem
from app.crud import SourceCRUD
from app.api.schemas import IngestPausedResponse
from app.core.constants import SourceItemProcessStatus
from app.core.exceptions import DocumentPausedException


class IngestItemStateService:
    """
    负责单个 SourceItem 的状态管理：请求暂停 / 可恢复检查 / 暂停检查点 / 状态更新包装
    """

    def __init__(self, *, source_crud: SourceCRUD):
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

    async def mark_processing(self, source_item: SourceItem) -> None:
        """将文档状态标记为 PROCESSING"""
        await self.source_crud.update_source_item_status(
            source_item, SourceItemProcessStatus.PROCESSING
        )

    async def mark_failed(self, source_item: SourceItem) -> None:
        """将文档状态标记为 FAILED"""
        await self.source_crud.update_source_item_status(
            source_item, SourceItemProcessStatus.FAILED
        )

    async def mark_completed(self, source_item: SourceItem) -> None:
        """将文档状态标记为 COMPLETED"""
        await self.source_crud.update_source_item_status(
            source_item, SourceItemProcessStatus.COMPLETED
        )
