from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.schemas import ProjectCreate, ProjectRead
from app.db.models import Projects


class ProjectService:
    async def create_project(
        self, session: AsyncSession, project_data: ProjectCreate
    ) -> ProjectRead:
        """创建新的项目，并返回项目详情"""
        new_project = Projects(**project_data.model_dump())
        session.add(new_project)
        await session.flush()  # 获取新项目的 UID
        return ProjectRead.model_validate(new_project)

    async def get_projects(
        self, session: AsyncSession, *, limit: int = 5, offset: int = 0
    ) -> list[ProjectRead]:
        """获取项目列表"""
        result = await session.execute(
            select(Projects)
            .offset(offset)
            .limit(limit)
            .order_by(Projects.created_at.desc())
        )
        projects = result.scalars().all()
        return [ProjectRead.model_validate(project) for project in projects]


def get_project_service() -> ProjectService:
    """项目服务工厂函数，提供 ProjectService 实例"""
    return ProjectService()
