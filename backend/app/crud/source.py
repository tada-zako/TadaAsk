from typing import Sequence

from sqlalchemy import select, func, delete, insert, update
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Source, SourceItem, DocumentContent, DocumentChunk
from app.db.schemas import (
    SourceInternal,
    SourceUpdate,
    SourceWithItemsCount,
    SourceItemInternal,
    DocumentChunkInternal,
    DocumentContentInternal,
)
from app.core.constants import SourceItemProcessStatus, SourceProcessStatus


class SourceCRUD:
    """数据源的 CRUD 操作"""

    def __init__(self, session: AsyncSession):
        self.session = session

    # =====================
    # Source 相关操作
    # =====================
    async def create_source(self, source_data: SourceInternal) -> Source:
        """创建新的数据源记录"""
        data = source_data.model_dump()
        if source_data.web_crawl_config is not None:
            # 避免 AnyHttpUrl 类型字段直接转换为 ORM 对象
            data["web_crawl_config"] = source_data.web_crawl_config.model_dump(
                mode="json"
            )

        new_source = Source(**data)
        self.session.add(new_source)
        await self.session.flush()  # 获取新数据源的 UID
        return new_source

    async def get_source_by_uid(self, source_uid: str) -> Source | None:
        """根据数据源 UID 获取数据源详情"""
        result = await self.session.execute(
            select(Source).where(Source.uid == source_uid)
        )
        return result.scalars().first()

    async def get_sources_by_uids(self, *, source_uids: list[str]) -> Sequence[Source]:
        """根据数据源 UID 列表批量获取数据源详情"""
        if not source_uids:
            return []

        result = await self.session.execute(
            select(Source).where(Source.uid.in_(source_uids))
        )
        return result.scalars().all()

    async def list_sources(
        self, *, limit: int = 10, offset: int = 0
    ) -> Sequence[Source]:
        """获取数据源列表，支持分页"""
        result = await self.session.execute(
            select(Source)
            .offset(offset)
            .limit(limit)
            .order_by(Source.created_at.desc())
        )
        return result.scalars().all()

    async def get_source_by_name(self, source_name: str) -> Source | None:
        """根据数据源名称获取数据源详情"""
        result = await self.session.execute(
            select(Source).where(Source.source_name == source_name)
        )
        return result.scalars().first()

    async def get_sources_with_items_count(
        self, *, limit: int = 5, offset: int = 0
    ) -> list[SourceWithItemsCount]:
        """获取附带数据项数量的数据源列表"""
        result = await self.session.execute(
            select(
                Source,
                func.count(SourceItem.id).label("items_count"),
            )
            .outerjoin(SourceItem, Source.id == SourceItem.source_id)
            .group_by(Source.uid)
            .offset(offset)
            .limit(limit)
            .order_by(Source.created_at.desc())
        )
        source_with_counts = []
        for source, items_count in result.all():
            source.items_count = items_count  # 动态添加 items_count 属性
            source_with_counts.append(SourceWithItemsCount.model_validate(source))

        return source_with_counts

    async def delete_source_by_id(self, source_id: int) -> bool:
        """根据数据源 ID 删除数据源，返回是否删除成功"""
        result = await self.session.execute(
            select(Source).where(Source.id == source_id)
        )
        source = result.scalars().first()
        if source:
            await self.session.delete(source)
            return True
        return False

    async def update_source(
        self,
        *,
        source: Source,
        source_data: SourceUpdate,
        reset_status: SourceProcessStatus | None = None,
    ) -> Source:
        """更新数据源基础信息"""
        data = source_data.model_dump(exclude_unset=True, mode="json")
        for key, value in data.items():
            setattr(source, key, value)

        if reset_status is not None:
            source.status = reset_status

        await self.session.flush()
        return source

    async def update_source_status(
        self, source: Source, new_status: SourceProcessStatus
    ) -> Source:
        """更新数据源的处理状态"""
        source.status = new_status
        return source

    async def count_source_items_by_source_id(self, *, source_id: int) -> int:
        """统计数据源下的数据项数量"""
        result = await self.session.execute(
            select(func.count(SourceItem.id)).where(SourceItem.source_id == source_id)
        )
        return result.scalar_one()

    # =====================
    # SourceItem 相关操作
    # =====================
    async def get_source_item_by_id(self, item_id: int) -> SourceItem | None:
        """根据数据项 ID 获取数据项详情"""
        result = await self.session.execute(
            select(SourceItem).where(SourceItem.id == item_id)
        )
        return result.scalars().first()

    async def get_source_item_by_uid(self, item_uid: str) -> SourceItem | None:
        """根据数据项 UID 获取数据项详情"""
        result = await self.session.execute(
            select(SourceItem).where(SourceItem.uid == item_uid)
        )
        return result.scalars().first()

    async def get_source_item_by_uid_for_source(
        self, source_id: int, item_uid: str
    ) -> SourceItem | None:
        """根据数据项 UID 和数据源 ID 获取数据项详情"""
        result = await self.session.execute(
            select(SourceItem).where(
                SourceItem.uid == item_uid,
                SourceItem.source_id == source_id,
            )
        )
        return result.scalars().first()

    async def get_source_item_by_uid_for_source_uid(
        self, source_uid: str, item_uid: str
    ) -> SourceItem | None:
        """根据数据项 UID 和数据源 UID 获取数据项详情"""
        result = await self.session.execute(
            select(SourceItem)
            .join(Source, Source.id == SourceItem.source_id)
            .where(
                SourceItem.uid == item_uid,
                Source.uid == source_uid,
            )
        )
        return result.scalars().first()

    async def get_source_item_by_item_key(
        self, *, source: Source, item_key: str
    ) -> SourceItem | None:
        """根据 item_key 获取数据项详情"""
        result = await self.session.execute(
            select(SourceItem).where(
                SourceItem.item_key == item_key,
                SourceItem.source_id == source.id,
            )
        )
        return result.scalars().first()

    async def add_source_items(
        self,
        source: Source,
        items_data: list[SourceItemInternal],
    ) -> Sequence[SourceItem]:
        """为指定数据源创建数据项"""
        new_items = []
        for item_data in items_data:
            new_item = SourceItem(
                **item_data.model_dump(),
            )
            source.source_items.append(new_item)
            new_items.append(new_item)

        await self.session.flush()  # 获取新数据项的完整字段
        return new_items

    async def upsert_source_item_by_item_key(
        self,
        source: Source,
        item_data: SourceItemInternal,
    ) -> SourceItem:
        """根据 item_key 更新或插入数据项"""
        result = await self.session.execute(
            select(SourceItem).where(
                SourceItem.item_key == item_data.item_key,
                SourceItem.source_id == source.id,
            )
        )
        existing_item = result.scalars().first()

        if existing_item:
            # 更新现有数据项的字段
            for key, value in item_data.model_dump(exclude_unset=True).items():
                setattr(existing_item, key, value)
            return existing_item
        else:
            # 创建新数据项
            new_item = SourceItem(source_id=source.id, **item_data.model_dump())
            self.session.add(new_item)
            await self.session.flush()  # 获取新数据项的完整字段
            return new_item

    async def delete_source_item_by_id(self, item_id: int) -> bool:
        """根据数据项 ID 删除数据项，返回是否删除成功"""
        result = await self.session.execute(
            select(SourceItem).where(SourceItem.id == item_id)
        )
        item = result.scalars().first()
        if item:
            await self.session.delete(item)
            return True
        return False

    async def list_source_items_by_source_id(
        self, *, source_id: int, limit: int = 15, offset: int = 0
    ) -> Sequence[SourceItem]:
        """根据数据源 ID 获取数据项列表"""
        result = await self.session.execute(
            select(SourceItem)
            .where(SourceItem.source_id == source_id)
            .offset(offset)
            .limit(limit)
            .order_by(SourceItem.updated_at.desc())
        )
        return result.scalars().all()

    async def list_source_item_filenames_by_source_id(
        self, *, source_id: int
    ) -> Sequence[str]:
        """根据数据源 ID 获取数据项的文件名列表"""
        stmt = select(SourceItem.filename).where(SourceItem.source_id == source_id)

        result = await self.session.execute(stmt)
        filenames = result.scalars().all()
        return [name for name in filenames if name is not None]

    async def list_source_item_storage_keys_by_source_id(
        self, *, source_id: int
    ) -> Sequence[str]:
        """根据数据源 ID 获取本地存储 key 列表"""
        stmt = select(SourceItem.storage_key).where(
            SourceItem.source_id == source_id,
            SourceItem.storage_key.is_not(None),
        )
        result = await self.session.execute(stmt)
        storage_keys = result.scalars().all()
        return [key for key in storage_keys if key is not None]

    async def get_source_items_by_uids_for_source(
        self, source_id: int, item_uids: list[str]
    ) -> Sequence[SourceItem]:
        """基于数据源 ID 和数据项 UID 列表获取数据项详情列表"""
        if not item_uids:
            return []

        result = await self.session.execute(
            select(SourceItem).where(
                SourceItem.source_id == source_id,
                SourceItem.uid.in_(item_uids),
            )
        )
        return result.scalars().all()

    async def update_source_item_status(
        self, source_item: SourceItem, new_status: SourceItemProcessStatus
    ) -> SourceItem:
        """更新数据项的处理状态"""
        source_item.status = new_status
        return source_item

    async def bulk_update_source_items_status(
        self,
        source: Source,
        source_item_uids: list[str],
    ) -> None:
        """
        根据数据源和数据项 UID 列表批量更新数据项的处理状态为 PAUSE_REQUESTED
        """
        stmt = (
            update(SourceItem)
            .where(
                SourceItem.source_id == source.id,
                SourceItem.uid.in_(source_item_uids),
                SourceItem.status == SourceItemProcessStatus.PROCESSING,
            )
            .values(status=SourceItemProcessStatus.PAUSE_REQUESTED)
            .execution_options(synchronize_session="fetch")
        )
        await self.session.execute(stmt)

    async def claim_source_item_for_ingest(
        self,
        *,
        source_uid: str,
        source_item_uid: str,
        allowed_statuses: list[SourceItemProcessStatus] | None = None,
    ) -> bool:
        """
        声明 source_item 进入 ingest 流程；
        确保并发请求同一个 source_item_uid 时，
        只有一个请求能成功 claim 到该数据项进行处理
        """
        claim_statuses = allowed_statuses or [
            SourceItemProcessStatus.PENDING,
            SourceItemProcessStatus.PAUSED,
            SourceItemProcessStatus.FAILED,
        ]
        source_id_stmt = (
            select(Source.id).where(Source.uid == source_uid).scalar_subquery()
        )
        stmt = (
            update(SourceItem)
            .where(
                SourceItem.uid == source_item_uid,
                SourceItem.source_id == (source_id_stmt),
                SourceItem.status.in_(claim_statuses),
            )
            .values(status=SourceItemProcessStatus.PROCESSING)
        )
        result = await self.session.execute(stmt)
        return result.rowcount == 1  # type: ignore[attr-defined]

    async def list_vector_ids_by_source_item_id(
        self, source_item_id: int
    ) -> Sequence[str]:
        """根据数据项 ID 获取关联的向量 ID 列表"""
        result = await self.session.execute(
            select(DocumentChunk.vector_id).where(
                DocumentChunk.source_item_id == source_item_id
            )
        )
        return result.scalars().all()

    async def get_source_and_item_by_uid(
        self, *, source_uid: str, source_item_uid: str
    ) -> tuple[Source, SourceItem] | None:
        """根据数据源 UID 和数据项 UID 获取数据源和数据项详情"""
        result = await self.session.execute(
            select(Source, SourceItem)
            .join(SourceItem, SourceItem.source_id == Source.id)
            .where(
                Source.uid == source_uid,
                SourceItem.uid == source_item_uid,
            )
        )
        row = result.first()
        if row:
            return tuple(row)
        return None

    async def get_source_and_item_with_content_by_uid(
        self, *, source_uid: str, source_item_uid: str
    ) -> tuple[Source, SourceItem] | None:
        """根据数据源 UID 和数据项 UID 获取数据源和数据项详情，包含 document_content"""
        result = await self.session.execute(
            select(Source, SourceItem)
            .join(SourceItem, SourceItem.source_id == Source.id)
            .options(
                selectinload(SourceItem.document_content)
            )  # 级联加载 document_content
            .where(
                Source.uid == source_uid,
                SourceItem.uid == source_item_uid,
            )
        )
        row = result.first()
        if row:
            return tuple(row)
        return None

    # =====================
    # DocumentContent 相关操作
    # =====================
    async def upsert_document_content(
        self,
        source_item: SourceItem,
        content_data: DocumentContentInternal,
    ) -> None:
        """
        更新或插入数据项的 document_content
        """
        existing_content = await source_item.awaitable_attrs.document_content

        if existing_content:
            for key, value in content_data.model_dump(exclude_unset=True).items():
                setattr(existing_content, key, value)
        else:
            new_content = DocumentContent(**content_data.model_dump())
            source_item.document_content = new_content

    # =====================
    # DocumentChunk 相关操作
    # =====================
    async def bulk_insert_document_chunks(
        self, chunks_data: list[DocumentChunkInternal]
    ):
        """批量插入 DocumentChunk 记录"""
        if not chunks_data:
            return

        chunk_dicts = [chunk_data.model_dump() for chunk_data in chunks_data]
        await self.session.execute(
            insert(DocumentChunk),
            chunk_dicts,
        )

    async def delete_document_chunks_by_source_item_id(
        self, source_item_id: int
    ) -> int:
        """根据数据项 ID 删除关联的 DocumentChunk 记录，返回删除的记录数量"""
        stmt = delete(DocumentChunk).where(
            DocumentChunk.source_item_id == source_item_id
        )
        result = await self.session.execute(stmt)
        # NOTE: 这里的 rowcount 未验证；尚不确定 result 确实存在 rowcount 属性
        return result.rowcount  # type: ignore
