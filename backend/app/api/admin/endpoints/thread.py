from typing import Annotated

from fastapi import APIRouter, Query
from loguru import logger

from ...deps import ThreadServiceDeps
from app.db.schemas import (
    ThreadCreate,
    ThreadRead,
    ChatMessageRead,
)
from app.core.config import settings

router = APIRouter(prefix="/project", tags=["Project-Thread"])


@router.post("/thread/new", response_model=ThreadRead)
async def create_thread(payload: ThreadCreate, thread_service: ThreadServiceDeps):
    """
    创建新的工作区线程

    Args:
        payload: 包含 thread 的 display_name 和 workspace_id 的请求体
        thread_service: ThreadService 实例，通过依赖注入获取

    Returns:
        创建成功的线程信息
    """
    # 配置默认的 chat_model，如果用户没有指定
    if not payload.model:
        payload.model = settings.gemini_model_perf or "gemini-2.5-flash"

    logger.info(
        f"创建新的对话，thread_name={payload.thread_name}, chat_model={payload.model}"
    )

    # 调用业务代码创建线程
    thread = await thread_service.create_thread(payload)
    return thread


@router.get("/threads", response_model=list[ThreadRead])
async def list_threads(
    thread_service: ThreadServiceDeps,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """
    获取工作区内的所有线程列表

    Args:
        thread_service: ThreadService 实例，通过依赖注入获取
        limit: 每页线程数量，默认为 10，范围 1-100
        offset: 偏移量，用于分页，默认为 0

    Returns:
        工作区内的线程列表
    """
    return await thread_service.get_threads(limit=limit, offset=offset)


@router.get("/thread/{thread_uid}/history", response_model=list[ChatMessageRead])
async def get_thread_history(
    thread_uid: str,
    thread_service: ThreadServiceDeps,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """
    获取指定线程的历史消息

    Args:
        thread_uid: 线程 UID
        thread_service: ThreadService 实例，通过依赖注入获取
        limit: 每页消息数量，默认为 10，范围 1-100
        offset: 偏移量，用于分页，默认为 0

    Returns:
        指定线程的历史消息列表
    """
    return await thread_service.get_thread_history(
        thread_uid=thread_uid, limit=limit, offset=offset
    )
