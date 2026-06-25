from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query, HTTPException, Path
from loguru import logger
from sqlalchemy.exc import IntegrityError

from ...deps import (
    ModelProfileCRUDeps,
    ProjectCRUDeps,
    SourceCRUDeps,
    ValidProjectDeps,
)
from app.db.models import ModelProfile, ProjectWidget, Provider, Source
from app.db.schemas import (
    ProjectCreate,
    ProjectRead,
    ProjectSettingsRead,
    ProjectSettingsUpdate,
    ProjectUpdate,
    ProjectWidgetCreate,
    ProjectWidgetRead,
    ProjectWidgetUpdate,
    SourceRead,
)

router = APIRouter()


async def resolve_default_model_refs(
    payload: Annotated[
        ProjectSettingsUpdate, Body(..., description="Project settings 更新数据")
    ],
    model_profile_crud: ModelProfileCRUDeps,
) -> tuple[bool, Provider | None, ModelProfile | None]:
    """解析 visitor 默认 provider/model 的 UID 输入。"""
    provider_and_model_exception = HTTPException(
        status_code=400,
        detail="visitor default provider and model profile must be configured together",
    )

    # 判断 provider, model_profile 字段是否由前端主动设置
    provider_field_set = "visitor_default_provider_uid" in payload.model_fields_set
    model_field_set = "visitor_default_model_profile_uid" in payload.model_fields_set

    if not provider_field_set and not model_field_set:
        return False, None, None

    if provider_field_set != model_field_set:
        # provider 和 model_profile 必须同时更新
        raise provider_and_model_exception

    provider_uid = payload.visitor_default_provider_uid
    model_uid = payload.visitor_default_model_profile_uid

    if provider_uid is None and model_uid is None:
        # 允许主动设置为 None
        return True, None, None

    if not provider_uid or not model_uid:
        # provider 和 model_profile 必须同时更新
        raise provider_and_model_exception

    provider_and_model = (
        await model_profile_crud.get_provider_with_model_profile_by_uid(
            provider_uid=provider_uid,
            model_uid=model_uid,
        )
    )
    if provider_and_model is None:
        raise HTTPException(
            status_code=404,
            detail="visitor default provider or model profile not found",
        )

    provider, model_profile = provider_and_model, provider_and_model.model_profiles[0]
    return True, provider, model_profile


async def resolve_sources_from_body(
    source_uids: Annotated[
        list[str],
        Body(
            ...,
            alias="sourceUids",
            embed=True,
            description="要处理的 source UID 列表",
        ),
    ],
    source_crud: SourceCRUDeps,
) -> list[Source]:
    """解析请求体中的 source UID 列表，返回按请求顺序排列的 source 实例。"""
    if not source_uids:
        raise HTTPException(status_code=400, detail="sourceUids must not be empty")

    source_uids = list(dict.fromkeys(source_uids))  # 保留顺序去重
    sources = await source_crud.get_sources_by_uids(source_uids=source_uids)
    source_by_uid = {source.uid: source for source in sources}

    # 检查是否有不存在的 source UID
    missing_source_uids = [uid for uid in source_uids if uid not in source_by_uid]
    if missing_source_uids:
        raise HTTPException(
            status_code=404,
            detail=f"Sources not found for UIDs: {missing_source_uids}",
        )

    return [source_by_uid[uid] for uid in source_uids]


RequestSourcesDeps = Annotated[list[Source], Depends(resolve_sources_from_body)]


async def valid_project_widget(
    project: ValidProjectDeps,
    project_crud: ProjectCRUDeps,
    widget_uid: Annotated[str, Path(..., description="Widget UID")],
) -> ProjectWidget:
    """验证 widget UID 是否属于当前 project"""
    widget = await project_crud.get_project_widget_by_uid(
        project_id=project.id,
        widget_uid=widget_uid,
    )
    if not widget:
        raise HTTPException(status_code=404, detail="Project widget not found")
    return widget


ValidProjectWidgetDeps = Annotated[ProjectWidget, Depends(valid_project_widget)]


@router.post("/new", response_model=ProjectRead)
async def create_project(
    payload: Annotated[ProjectCreate, Body(..., description="Project 创建数据")],
    project_crud: ProjectCRUDeps,
):
    """
    创建新的项目

    Args:
        payload: 包含 project 的 display_name 的请求体
        project_crud: 通过依赖注入获取的 ProjectCRUD 实例

    Returns:
        创建成功的项目信息
    """
    try:
        project = await project_crud.create_project(project_data=payload)
    except IntegrityError as exc:
        logger.warning(f"创建 project 失败，存在唯一约束冲突：{exc}")
        raise HTTPException(
            status_code=400,
            detail="project with the same name already exists",
        ) from exc

    return ProjectRead.model_validate(project)


@router.get("/list", response_model=list[ProjectRead])
async def list_projects(
    project_crud: ProjectCRUDeps,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """
    获取项目列表

    Args:
        project_crud: 通过依赖注入获取的 ProjectCRUD 实例
        limit: 分页参数，限制返回的项目数量
        offset: 分页参数，指定返回项目的起始位置

    Returns:
        项目列表
    """

    return await project_crud.list_projects(limit=limit, offset=offset)


@router.get("/{project_uid}", response_model=ProjectRead)
async def get_project(
    project: ValidProjectDeps,
):
    """
    获取项目详情

    Args:
        project: 通过依赖注入获取的有效项目实例

    Returns:
        项目详情
    """
    return project


@router.patch("/{project_uid}", response_model=ProjectRead)
async def update_project(
    project: ValidProjectDeps,
    payload: Annotated[ProjectUpdate, Body(..., description="Project 更新数据")],
    project_crud: ProjectCRUDeps,
):
    """更新项目基础信息"""
    try:
        updated_project = await project_crud.update_project(
            project=project,
            project_data=payload,
        )
    except IntegrityError as exc:
        logger.warning(f"更新 project 失败，存在唯一约束冲突：{exc}")
        raise HTTPException(
            status_code=400,
            detail="project with the same name already exists",
        ) from exc

    return ProjectRead.model_validate(updated_project)


@router.delete("/{project_uid}")
async def delete_project(
    project: ValidProjectDeps,
    project_crud: ProjectCRUDeps,
):
    """
    删除项目

    Args:
        project: 通过依赖注入获取的有效项目实例
        project_crud: 通过依赖注入获取的 ProjectCRUD 实例

    Returns:
        删除结果
    """
    success = await project_crud.delete_project_by_id(project_id=project.id)
    if success:
        return {
            "uid": project.uid,
            "status": "deleted",
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to delete project")


@router.get("/{project_uid}/widgets", response_model=list[ProjectWidgetRead])
async def list_project_widgets(
    project: ValidProjectDeps,
    project_crud: ProjectCRUDeps,
):
    """获取 project 下的 widget 部署实例列表"""
    widgets = await project_crud.list_project_widgets(project_id=project.id)
    return [ProjectWidgetRead.model_validate(widget) for widget in widgets]


@router.post("/{project_uid}/widgets", response_model=ProjectWidgetRead)
async def create_project_widget(
    project: ValidProjectDeps,
    payload: Annotated[
        ProjectWidgetCreate, Body(..., description="Project widget 创建数据")
    ],
    project_crud: ProjectCRUDeps,
):
    """为 project 创建 widget 部署实例"""
    try:
        widget = await project_crud.create_project_widget(
            project=project,
            widget_data=payload,
        )
    except IntegrityError as exc:
        logger.warning(f"创建 project widget 失败，存在唯一约束冲突：{exc}")
        raise HTTPException(
            status_code=400,
            detail="project widget with the same name already exists",
        ) from exc

    return ProjectWidgetRead.model_validate(widget)


@router.get("/{project_uid}/widgets/{widget_uid}", response_model=ProjectWidgetRead)
async def get_project_widget(widget: ValidProjectWidgetDeps):
    """获取 project widget 详情"""
    return ProjectWidgetRead.model_validate(widget)


@router.patch("/{project_uid}/widgets/{widget_uid}", response_model=ProjectWidgetRead)
async def update_project_widget(
    widget: ValidProjectWidgetDeps,
    payload: Annotated[
        ProjectWidgetUpdate, Body(..., description="Project widget 更新数据")
    ],
    project_crud: ProjectCRUDeps,
):
    """更新 project widget 部署实例"""
    try:
        updated_widget = await project_crud.update_project_widget(
            widget=widget,
            widget_data=payload,
        )
    except IntegrityError as exc:
        logger.warning(f"更新 project widget 失败，存在唯一约束冲突：{exc}")
        raise HTTPException(
            status_code=400,
            detail="project widget with the same name already exists",
        ) from exc

    return ProjectWidgetRead.model_validate(updated_widget)


@router.delete("/{project_uid}/widgets/{widget_uid}")
async def delete_project_widget(
    widget: ValidProjectWidgetDeps,
    project_crud: ProjectCRUDeps,
):
    """删除 project widget 部署实例"""
    success = await project_crud.delete_project_widget_by_id(widget_id=widget.id)
    if success:
        return {"uid": widget.uid, "status": "deleted"}
    raise HTTPException(status_code=500, detail="Failed to delete project widget")


@router.get("/{project_uid}/settings", response_model=ProjectSettingsRead)
async def get_project_settings(
    project: ValidProjectDeps,
    project_crud: ProjectCRUDeps,
):
    """获取 project settings 详情，包括关联的默认 provider 和 model profile 信息"""
    project_settings = await project_crud.get_project_settings_by_project_id(
        project_id=project.id
    )

    return ProjectSettingsRead.model_validate(project_settings)


@router.patch("/{project_uid}/settings", response_model=ProjectSettingsRead)
async def update_project_settings(
    project: ValidProjectDeps,
    payload: Annotated[
        ProjectSettingsUpdate, Body(..., description="Project settings 更新数据")
    ],
    project_crud: ProjectCRUDeps,
    model_profile_crud: ModelProfileCRUDeps,
):
    """更新 project settings"""
    project_settings = await project_crud.get_project_settings_by_project_id(
        project_id=project.id
    )

    # 解析 visitor 默认 provider/model 的 UID 输入
    update_default_model, provider, model_profile = await resolve_default_model_refs(
        payload=payload,
        model_profile_crud=model_profile_crud,
    )

    try:
        updated_settings = await project_crud.update_project_settings(
            project_settings=project_settings,
            settings_data=payload,
            update_default_model=update_default_model,  # 是否更新模型配置
            visitor_default_provider=provider,  # 允许为 None -> 不设置 provider-model
            visitor_default_model_profile=model_profile,
        )
    except IntegrityError as exc:
        logger.warning(f"更新 project settings 失败，存在唯一约束冲突：{exc}")
        raise HTTPException(
            status_code=400,
            detail="failed to update project settings",
        ) from exc

    return ProjectSettingsRead.model_validate(updated_settings)


@router.get("/{project_uid}/sources", response_model=list[SourceRead])
async def list_project_sources(
    project: ValidProjectDeps,
    project_crud: ProjectCRUDeps,
):
    """获取 project 已绑定的数据源列表"""
    sources = await project_crud.list_sources_by_project_id(project_id=project.id)
    return [SourceRead.model_validate(source) for source in sources]


@router.post("/{project_uid}/sources")
async def bind_project_sources(
    project: ValidProjectDeps,
    sources: RequestSourcesDeps,
    project_crud: ProjectCRUDeps,
):
    """将已有 sources 批量绑定到 project；
    幂等操作，允许重复绑定同一 source"""
    source_ids = [source.id for source in sources]

    try:
        inserted_count = await project_crud.bind_sources_to_project(
            project_id=project.id,
            source_ids=source_ids,
        )
    except IntegrityError as exc:
        logger.warning(f"绑定 sources 到 project 失败：{exc}")
        raise HTTPException(
            status_code=400,
            detail="failed to bind sources to project",
        ) from exc

    return {
        "projectUid": project.uid,
        "sourceUids": [source.uid for source in sources],
        "insertedCount": inserted_count,
        "status": "bound",
    }


@router.delete("/{project_uid}/sources")
async def unbind_project_sources(
    project: ValidProjectDeps,
    sources: RequestSourcesDeps,
    project_crud: ProjectCRUDeps,
):
    """批量解除 sources 与 project 的绑定关系；
    幂等操作，允许解除未绑定的 source"""
    source_ids = [source.id for source in sources]

    deleted_count = await project_crud.unbind_sources_from_project(
        project_id=project.id,
        source_ids=source_ids,
    )

    return {
        "projectUid": project.uid,
        "sourceUids": [source.uid for source in sources],
        "deletedCount": deleted_count,
        "status": "unbound",
    }
