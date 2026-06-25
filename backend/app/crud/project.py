from typing import Sequence

from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.db.models import (
    ModelProfile,
    Project,
    ProjectSettings,
    ProjectSourceLink,
    ProjectWidget,
    Provider,
    Source,
)
from app.db.schemas import (
    ProjectCreate,
    ProjectSettingsUpdate,
    ProjectUpdate,
    ProjectWidgetCreate,
    ProjectWidgetUpdate,
)


class ProjectCRUD:
    """项目的 CRUD 操作"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_project(self, project_data: ProjectCreate) -> Project:
        """创建新的项目，并同时创建默认项目设置"""
        new_project = Project(**project_data.model_dump())
        new_project.project_settings = ProjectSettings()
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

    # ====================
    # ProjectSettings 相关操作
    # ====================
    async def get_project_settings_by_project_id(
        self, *, project_id: int
    ) -> ProjectSettings:
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
        return result.scalars().one()

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

    # ====================
    # ProjectWidget 相关操作
    # ====================
    async def create_project_widget(
        self, *, project: Project, widget_data: ProjectWidgetCreate
    ) -> ProjectWidget:
        """为 project 创建 widget 部署实例"""
        new_widget = ProjectWidget(
            project_id=project.id,
            **widget_data.model_dump(),
        )
        self.session.add(new_widget)
        await self.session.flush()
        return new_widget

    async def list_project_widgets(self, *, project_id: int) -> Sequence[ProjectWidget]:
        """获取项目下的 widget 部署实例列表"""
        stmt = (
            select(ProjectWidget)
            .where(ProjectWidget.project_id == project_id)
            .order_by(ProjectWidget.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_project_widget_by_uid(
        self, *, project_id: int, widget_uid: str
    ) -> ProjectWidget | None:
        """根据项目 ID 和 widget UID 获取部署实例"""
        stmt = select(ProjectWidget).where(
            ProjectWidget.project_id == project_id,
            ProjectWidget.uid == widget_uid,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def update_project_widget(
        self, *, widget: ProjectWidget, widget_data: ProjectWidgetUpdate
    ) -> ProjectWidget:
        """更新 widget 部署实例"""
        for key, value in widget_data.model_dump(exclude_unset=True).items():
            setattr(widget, key, value)

        await self.session.flush()
        return widget

    async def delete_project_widget_by_id(self, *, widget_id: int) -> bool:
        """根据 widget ID 删除部署实例，返回是否删除成功"""
        result = await self.session.execute(
            select(ProjectWidget).where(ProjectWidget.id == widget_id)
        )
        widget = result.scalars().first()
        if widget:
            await self.session.delete(widget)
            return True
        return False

    # ====================
    # Project-Source 关联操作
    # ====================
    async def list_sources_by_project_id(self, *, project_id: int) -> Sequence[Source]:
        """获取项目绑定的数据源列表"""
        stmt = (
            select(Source)
            .join(ProjectSourceLink, ProjectSourceLink.source_id == Source.id)
            .where(ProjectSourceLink.project_id == project_id)
            .order_by(Source.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_project_source_links(
        self, *, project_id: int, source_ids: list[int]
    ) -> Sequence[ProjectSourceLink]:
        """批量获取项目与数据源的绑定关系"""
        if not source_ids:
            return []

        stmt = select(ProjectSourceLink).where(
            ProjectSourceLink.project_id == project_id,
            ProjectSourceLink.source_id.in_(source_ids),
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def bind_sources_to_project(
        self, *, project_id: int, source_ids: list[int]
    ) -> int:
        """将多个数据源批量绑定到项目，忽略已存在的绑定关系"""
        source_ids = list(dict.fromkeys(source_ids))
        if not source_ids:
            return 0

        values = [
            {"project_id": project_id, "source_id": source_id}
            for source_id in source_ids
        ]
        stmt = insert(ProjectSourceLink).values(values)
        # 使用 on_conflict_do_nothing 忽略已存在的绑定关系，确保幂等性
        stmt = stmt.on_conflict_do_nothing(index_elements=["project_id", "source_id"])
        result = await self.session.execute(stmt)
        return result.rowcount or 0  # type: ignore[attr-defined]

    async def unbind_sources_from_project(
        self, *, project_id: int, source_ids: list[int]
    ) -> int:
        """批量解除项目与数据源的绑定关系，返回删除数量"""
        source_ids = list(dict.fromkeys(source_ids))
        if not source_ids:
            return 0

        stmt = delete(ProjectSourceLink).where(
            ProjectSourceLink.project_id == project_id,
            ProjectSourceLink.source_id.in_(source_ids),
        )
        result = await self.session.execute(stmt)
        return result.rowcount or 0  # type: ignore[attr-defined]
