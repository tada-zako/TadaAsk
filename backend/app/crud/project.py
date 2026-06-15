from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Project, ProjectSourceLink, ProjectSettings
from app.db.schemas import ProjectCreate


class ProjectCRUD:
    """项目的 CRUD 操作"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_project(self, project_data: ProjectCreate) -> Project:
        """创建新的项目，并返回创建的项目实例"""
        new_project = Project(**project_data.model_dump())
        self.session.add(new_project)
        await self.session.flush()  # 获取新项目的 UID
        return new_project

    async def list_projects(
        self, *, limit: int = 5, offset: int = 0
    ) -> Sequence[Project]:
        """获取项目列表"""
        result = await self.session.execute(
            select(Project)
            .offset(offset)
            .limit(limit)
            .order_by(Project.created_at.desc())
        )
        projects = result.scalars().all()
        return projects

    async def get_project_by_uid(self, project_uid: str) -> Project | None:
        """根据项目 UID 获取项目详情"""
        result = await self.session.execute(
            select(Project).where(Project.uid == project_uid)
        )
        return result.scalars().first()

    async def delete_project_by_id(self, project_id: int) -> bool:
        """根据项目 ID 删除项目，返回是否删除成功"""
        result = await self.session.execute(
            select(Project).where(Project.id == project_id)
        )
        project = result.scalars().first()
        if project:
            await self.session.delete(project)
            return True
        return False

    async def bind_source_to_project(
        self, *, project_id: int, source_id: int
    ) -> ProjectSourceLink:
        """将数据源绑定到项目，返回绑定关系实例"""
        link = ProjectSourceLink(project_id=project_id, source_id=source_id)
        self.session.add(link)
        await self.session.flush()
        return link
