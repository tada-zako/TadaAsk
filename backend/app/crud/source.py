from typing import Sequence

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Sources, SourceItems
from app.db.schemas import (
    SourceInternal,
    SourceWithItemsCount,
    SourceItemInternal,
)


async def create_source(session: AsyncSession, source_data: SourceInternal) -> Sources:
    """创建新的数据源记录"""
    new_source = Sources(**source_data.model_dump())
    session.add(new_source)
    await session.flush()  # 获取新数据源的 UID
    return new_source


async def get_source_by_uid(session: AsyncSession, source_uid: str) -> Sources | None:
    """根据数据源 UID 获取数据源详情"""
    result = await session.execute(select(Sources).where(Sources.uid == source_uid))
    return result.scalars().first()


async def get_sources_with_items_count(
    session: AsyncSession, *, limit: int = 5, offset: int = 0
) -> list[SourceWithItemsCount]:
    """获取附带数据项数量的数据源列表"""
    result = await session.execute(
        select(
            Sources,
            func.count(SourceItems.id).label("items_count"),
        )
        .outerjoin(SourceItems, Sources.id == SourceItems.source_id)
        .group_by(Sources.uid)
        .offset(offset)
        .limit(limit)
        .order_by(Sources.created_at.desc())
    )
    source_with_counts = []
    for source, items_count in result.all():
        source.items_count = items_count  # 动态添加 items_count 属性
        source_with_counts.append(SourceWithItemsCount.model_validate(source))

    return source_with_counts


async def delete_source_by_id(session: AsyncSession, source_id: int) -> bool:
    """根据数据源 ID 删除数据源，返回是否删除成功"""
    result = await session.execute(select(Sources).where(Sources.id == source_id))
    source = result.scalars().first()
    if source:
        await session.delete(source)
        return True
    return False


async def create_source_item(
    session: AsyncSession, item_data: SourceItemInternal
) -> SourceItems:
    """创建新的数据项记录"""
    new_item = SourceItems(**item_data.model_dump())
    session.add(new_item)
    await session.flush()  # 获取新数据项的 ID
    return new_item


async def get_source_items_by_source_id(
    session: AsyncSession, *, source_id: int, limit: int = 15, offset: int = 0
) -> Sequence[SourceItems]:
    """根据数据源 ID 获取数据项列表"""
    result = await session.execute(
        select(SourceItems)
        .where(SourceItems.source_id == source_id)
        .offset(offset)
        .limit(limit)
        .order_by(SourceItems.updated_at.desc())
    )
    return result.scalars().all()
