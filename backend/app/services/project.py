from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.schemas import ProjectCreate, ProjectRead
from app.db.models import Projects


class ProjectService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_project(self, project_data: ProjectCreate) -> ProjectRead:
        """创建新的项目，并返回项目详情"""
        new_project = Projects(**project_data.model_dump())
        self.session.add(new_project)
        await self.session.flush()  # 获取新项目的 UID
        return ProjectRead.model_validate(new_project)

    async def get_projects(
        self, *, limit: int = 5, offset: int = 0
    ) -> list[ProjectRead]:
        """获取项目列表"""
        result = await self.session.execute(
            select(Projects)
            .offset(offset)
            .limit(limit)
            .order_by(Projects.created_at.desc())
        )
        projects = result.scalars().all()
        return [ProjectRead.model_validate(project) for project in projects]
