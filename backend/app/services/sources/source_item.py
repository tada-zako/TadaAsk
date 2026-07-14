import asyncio
from dataclasses import dataclass

from loguru import logger

from app.crud import SourceCRUD
from app.db.models import Source, SourceItem
from app.rag import VectorDatabase
from app.storage import FileDownloadTarget, FileStorage
from app.core.constants import SourceItemProcessStatus, SourceType
from app.core.exceptions import (
    SourceItemDeleteConflictError,
    SourceItemDownloadUnsupportedError,
)


# 不允许删除的状态集合
_DELETE_BLOCKED_STATUSES = {
    SourceItemProcessStatus.PROCESSING,
    SourceItemProcessStatus.PAUSE_REQUESTED,
}


@dataclass
class SourceItemDeleteResult:
    """Source item 删除结果结构体"""

    deleted_vector_count: int
    file_deleted: bool  # 是否删除文件


@dataclass
class SourceItemDownloadInfo:
    """Source item 下载信息"""

    target: FileDownloadTarget
    filename: str


class SourceItemService:
    """SourceItem 操作 service"""

    def __init__(
        self,
        *,
        source_crud: SourceCRUD,
        vector_db: VectorDatabase,
        file_storage: FileStorage,
    ):
        self.source_crud = source_crud
        self.vector_db = vector_db
        self.file_storage = file_storage

    async def delete_source_item(
        self,
        *,
        source: Source,
        source_item: SourceItem,
    ) -> SourceItemDeleteResult:
        """删除 SourceItem 及其相关数据"""
        if source_item.status in _DELETE_BLOCKED_STATUSES:
            # 目标 source item 状态不支持删除
            raise SourceItemDeleteConflictError(
                "Source item is busy, pause it or wait until processing finishes"
            )

        storage_key = source_item.storage_key  # 文件存储 key
        vector_ids = list(
            await self.source_crud.list_vector_ids_by_source_item_id(
                source_item_id=source_item.id
            )
        )
        if vector_ids:
            # 删除向量数据库中对应的向量数据
            await asyncio.to_thread(
                self.vector_db.delete_data_from_collection,
                collection_name=source.collection_name,
                ids=vector_ids,
            )

        # 删除数据库记录
        deleted = await self.source_crud.delete_source_item_by_id(
            item_id=source_item.id
        )
        if not deleted:
            raise ValueError("Source item not found")

        file_deleted = False
        if storage_key:
            try:
                # 删除对应的存储文件
                file_deleted = await self.file_storage.delete_file(key=storage_key)
            except Exception as exc:
                logger.warning(
                    f"Failed to delete storage file for source item {source_item.uid}: {exc}"
                )

        return SourceItemDeleteResult(
            deleted_vector_count=len(vector_ids),
            file_deleted=file_deleted,
        )

    async def rename_source_item(
        self,
        *,
        source: Source,
        source_item: SourceItem,
        title: str,
    ) -> SourceItem:
        """重命名 SourceItem 展示字段，不修改 storage_key 或物理文件。"""
        # local file 类型 source 额外修改 filename 字段
        filename = title if source.source_type == SourceType.LOCAL_FILE else None

        return await self.source_crud.rename_source_item(
            source_item=source_item,
            title=title,
            filename=filename,
        )

    async def get_download_info(
        self,
        *,
        source: Source,
        source_item: SourceItem,
    ) -> SourceItemDownloadInfo:
        """获取本地文件下载信息；web crawl 暂不支持下载。"""
        if source.source_type != SourceType.LOCAL_FILE:
            # 不支持下载
            raise SourceItemDownloadUnsupportedError(
                "Source item type does not support download"
            )

        if not source_item.storage_key:
            raise FileNotFoundError("Source item file not found")

        try:
            target = await self.file_storage.get_download_target(
                key=source_item.storage_key
            )
        except ValueError as exc:
            raise FileNotFoundError("Source item file not found") from exc

        return SourceItemDownloadInfo(
            target=target,
            filename=source_item.filename or source_item.title,
        )
