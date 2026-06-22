from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    ModelProfile,
    Project,
    ProjectSourceLink,
    ProjectSettings,
    Provider,
)
from app.db.schemas import (
    ProjectCreate,
    ProjectSettingsCreate,
    ProjectSettingsUpdate,
    ProjectUpdate,
)


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

    async def update_project(
        self, *, project: Project, project_data: ProjectUpdate
    ) -> Project:
        """更新项目配置"""
        for key, value in project_data.model_dump(exclude_unset=True).items():
            setattr(project, key, value)

        await self.session.flush()
        return project

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

    async def get_project_with_settings_by_uid(
        self, project_uid: str
    ) -> Project | None:
        """联合查询：加载 Project -> ProjectSettings -> Provider & ModelProfile"""
        stmt = (
            select(Project)
            .where(Project.uid == project_uid)
            .options(
                # 联合加载 ProjectSettings
                joinedload(Project.project_settings).options(
                    # 联合加载 Provider 和 ModelProfile
                    joinedload(ProjectSettings.visitor_default_provider),
                    joinedload(ProjectSettings.visitor_default_model_profile),
                )
            )
        )
        result = await self.session.execute(stmt)
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

    # ====================
    # ProjectSettings 相关操作
    # ====================
    async def create_project_settings(
        self,
        *,
        project: Project,
        settings_data: ProjectSettingsCreate,
        visitor_default_provider: Provider | None = None,
        visitor_default_model_profile: ModelProfile | None = None,
    ) -> ProjectSettings:
        """创建项目设置"""
        data = settings_data.model_dump(
            exclude_unset=True,
            exclude={
                "visitor_default_provider_uid",
                "visitor_default_model_profile_uid",
            },
        )
        new_settings = ProjectSettings(
            **data,
            project_id=project.id,
            visitor_default_provider=visitor_default_provider,
            visitor_default_model_profile=visitor_default_model_profile,
        )
        self.session.add(new_settings)
        await self.session.flush()
        return new_settings

    async def get_project_settings_by_project_id(
        self, *, project_id: int
    ) -> ProjectSettings | None:
        """根据项目 ID 获取项目设置，并加载默认 provider 与 model profile"""
        stmt = (
            select(ProjectSettings)
            .where(ProjectSettings.project_id == project_id)
            .options(
                joinedload(ProjectSettings.visitor_default_provider),
                joinedload(ProjectSettings.visitor_default_model_profile),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def update_project_settings(
        self,
        *,
        project_settings: ProjectSettings,
        settings_data: ProjectSettingsUpdate,
        update_default_model: bool = False,
        visitor_default_provider: Provider | None = None,
        visitor_default_model_profile: ModelProfile | None = None,
    ) -> ProjectSettings:
        """更新项目设置"""
        data = settings_data.model_dump(
            exclude_unset=True,
            exclude={
                "visitor_default_provider_uid",
                "visitor_default_model_profile_uid",
            },
        )
        for key, value in data.items():
            setattr(project_settings, key, value)

        if update_default_model:
            project_settings.visitor_default_provider = visitor_default_provider
            project_settings.visitor_default_model_profile = (
                visitor_default_model_profile
            )

        await self.session.flush()
        return project_settings

    async def delete_project_settings_by_id(self, project_settings_id: int) -> bool:
        """根据项目设置 ID 删除项目设置，返回是否删除成功"""
        result = await self.session.execute(
            select(ProjectSettings).where(ProjectSettings.id == project_settings_id)
        )
        project_settings = result.scalars().first()
        if project_settings:
            await self.session.delete(project_settings)
            return True
        return False
