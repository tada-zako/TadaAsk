from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Threads
from app.db.schemas import ThreadCreate


async def create_thread(session: AsyncSession, thread_data: ThreadCreate) -> Threads:
    """创建新的聊天线程，并返回创建的对话实例"""
    new_thread = Threads(**thread_data.model_dump())
    session.add(new_thread)
    await session.flush()  # 获取新线程的 UID
    return new_thread


async def get_threads(
    session: AsyncSession, *, limit: int = 5, offset: int = 0
) -> Sequence[Threads]:
    """获取所有聊天线程列表"""
    result = await session.execute(
        select(Threads).offset(offset).limit(limit).order_by(Threads.created_at.desc())
    )
    return result.scalars().all()
