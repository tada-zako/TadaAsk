from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Projects, ProjectSourceLinks
from app.db.schemas import ProjectCreate


async def create_project(
    session: AsyncSession, project_data: ProjectCreate
) -> Projects:
    """创建新的项目，并返回创建的项目实例"""
    new_project = Projects(**project_data.model_dump())
    session.add(new_project)
    await session.flush()  # 获取新项目的 UID
    return new_project


async def get_projects(
    session: AsyncSession, *, limit: int = 5, offset: int = 0
) -> Sequence[Projects]:
    """获取项目列表"""
    result = await session.execute(
        select(Projects)
        .offset(offset)
        .limit(limit)
        .order_by(Projects.created_at.desc())
    )
    projects = result.scalars().all()
    return projects


async def get_project_by_uid(
    session: AsyncSession, project_uid: str
) -> Projects | None:
    """根据项目 UID 获取项目详情"""
    result = await session.execute(select(Projects).where(Projects.uid == project_uid))
    return result.scalars().first()


async def delete_project_by_id(session: AsyncSession, project_id: int) -> bool:
    """根据项目 ID 删除项目，返回是否删除成功"""
    result = await session.execute(select(Projects).where(Projects.id == project_id))
    project = result.scalars().first()
    if project:
        await session.delete(project)
        return True
    return False


async def bind_source_to_project(
    session: AsyncSession, *, project_id: int, source_id: int
) -> ProjectSourceLinks:
    """将数据源绑定到项目，返回绑定关系实例"""
    link = ProjectSourceLinks(project_id=project_id, source_id=source_id)
    session.add(link)
    await session.flush()
    return link
