from typing import Annotated

from fastapi import APIRouter, Query, HTTPException

from ...deps import SessionDeps, ValidProjectDeps
from app.crud import project as project_crud
from app.db.schemas import ProjectCreate, ProjectRead

router = APIRouter()


@router.post("/new", response_model=ProjectRead)
async def create_project(
    payload: ProjectCreate,
    session: SessionDeps,
):
    """
    创建新的项目

    Args:
        payload: 包含 project 的 display_name 的请求体
        session: 数据库会话，通过依赖注入获取

    Returns:
        创建成功的项目信息
    """
    return await project_crud.create_project(session=session, project_data=payload)


@router.get("/list", response_model=list[ProjectRead])
async def list_projects(
    session: SessionDeps,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """
    获取项目列表

    Args:
        session: 数据库会话，通过依赖注入获取
        limit: 分页参数，限制返回的项目数量
        offset: 分页参数，指定返回项目的起始位置

    Returns:
        项目列表
    """

    return await project_crud.get_projects(session=session, limit=limit, offset=offset)


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


@router.delete("/{project_uid}")
async def delete_project(
    project: ValidProjectDeps,
    session: SessionDeps,
):
    """
    删除项目

    Args:
        project: 通过依赖注入获取的有效项目实例
        session: 数据库会话，通过依赖注入获取

    Returns:
        删除结果
    """
    success = await project_crud.delete_project_by_id(
        session=session, project_id=project.id
    )
    if success:
        return {
            "uid": project.uid,
            "status": "deleted",
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to delete project")
