import asyncio
from dataclasses import dataclass

from loguru import logger

from app.crud import SourceCRUD
from app.db.models import Source, SourceItem
from app.rag import VectorDatabase
from app.storage import FileStorage
from app.core.constants import SourceItemProcessStatus
from app.core.exceptions import SourceItemDeleteConflictError


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
