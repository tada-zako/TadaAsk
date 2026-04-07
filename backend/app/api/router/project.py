from typing import Annotated

from fastapi import APIRouter, Query

from ..deps import ProjectServiceDeps
from app.db.schemas import ProjectCreate, ProjectRead

router = APIRouter(prefix="/project", tags=["Project"])


@router.post("/new", response_model=ProjectRead)
async def create_project(
    payload: ProjectCreate,
    project_service: ProjectServiceDeps,
):
    """
    创建新的项目

    Args:
        payload: 包含 project 的 display_name 的请求体
        session: 数据库会话，通过依赖注入获取
        project_service: ProjectService 实例，通过依赖注入获取

    Returns:
        创建成功的项目信息
    """
    return await project_service.create_project(payload)


@router.get("/list", response_model=list[ProjectRead])
async def list_projects(
    project_service: ProjectServiceDeps,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """
    获取项目列表

    Args:
        project_service: ProjectService 实例，通过依赖注入获取
        limit: 分页参数，限制返回的项目数量
        offset: 分页参数，指定返回项目的起始位置

    Returns:
        项目列表
    """

    return await project_service.get_projects(limit=limit, offset=offset)
