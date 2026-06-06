from typing import Sequence

from sqlalchemy import select, func, delete, insert
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Source, SourceItem, DocumentContent, DocumentChunk
from app.db.schemas import (
    SourceInternal,
    SourceWithItemsCount,
    SourceItemInternal,
    DocumentChunkInternal,
)
from app.core.constants import SourceProcessStatus


class SourceCRUD:
    """数据源的 CRUD 操作"""

    def __init__(self, session: AsyncSession):
        self.session = session

    # =====================
    # Source 相关操作
    # =====================
    async def create_source(self, source_data: SourceInternal) -> Source:
        """创建新的数据源记录"""
        new_source = Source(**source_data.model_dump())
        self.session.add(new_source)
        await self.session.flush()  # 获取新数据源的 UID
        return new_source

    async def get_source_by_uid(self, source_uid: str) -> Source | None:
        """根据数据源 UID 获取数据源详情"""
        result = await self.session.execute(
            select(Source).where(Source.uid == source_uid)
        )
        return result.scalars().first()

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

    # =====================
    # SourceItem 相关操作
    # =====================
    async def get_source_item_by_id(self, item_id: int) -> SourceItem | None:
        """根据数据项 ID 获取数据项详情"""
        result = await self.session.execute(
            select(SourceItem).where(SourceItem.id == item_id)
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
                source_id=source.id,
            )
            source.source_items.append(new_item)
            new_items.append(new_item)

        await self.session.flush()  # 获取新数据项的完整字段
        return new_items

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
        result = await self.session.execute(
            select(SourceItem.filename).where(SourceItem.source_id == source_id)
        )
        return result.scalars().all()

    async def get_source_items_by_uids_with_document_for_source(
        self, source_id: int, item_uids: list[str]
    ) -> Sequence[SourceItem]:
        """
        基于数据源 ID 和数据项 UID 列表获取数据项详情列表
        级联查询 document 字段内容
        """
        if not item_uids:
            return []

        result = await self.session.execute(
            select(SourceItem)
            .options(
                selectinload(SourceItem.document_content)  # 级联加载 document 字段
            )
            .where(
                SourceItem.uid.in_(item_uids),
                SourceItem.source_id == source_id,
            )
        )
        return result.scalars().all()

    async def update_source_item_status(
        self, source_item: SourceItem, new_status: SourceProcessStatus
    ) -> SourceItem:
        """更新数据项的处理状态"""
        source_item.status = new_status
        return source_item

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

    # =====================
    # DocumentContent 相关操作
    # =====================
    async def upsert_document_content(
        self, source_item: SourceItem, content: str
    ) -> None:
        """
        更新或插入数据项的 document_content
        NOTE: 这里 source_item.document_content 的检查逻辑依赖于
                .options(selectinload(...)) 预先加载 document_content 字段；
                如果没有预加载，可能会导致会导致同步查询，阻塞异步流程
        """
        if source_item.document_content:
            source_item.document_content.content = content
        else:
            new_doc_content = DocumentContent(content=content)
            source_item.document_content = new_doc_content

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
