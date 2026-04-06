from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.core.db import get_db
from app.services.chat_thread import get_chat_thread_service, ChatThreadService
from app.core.schemas import (
    WorkspaceThreadCreate,
    WorkspaceThreadRead,
    WorkspaceChatRead,
)
from app.core.config import settings

router = APIRouter(prefix="/workspace", tags=["workspace"])


@router.post("/thread/new", response_model=WorkspaceThreadRead)
async def create_thread(
    payload: WorkspaceThreadCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
    thread_service: Annotated[ChatThreadService, Depends(get_chat_thread_service)],
):
    """
    创建新的工作区线程

    Args:
        payload: 包含 thread 的 display_name 和 workspace_id 的请求体
        session: 数据库会话，通过依赖注入获取
        thread_service: ChatThreadService 实例，通过依赖注入获取

    Returns:
        创建成功的线程信息
    """
    # 配置默认的 chat_model，如果用户没有指定
    if not payload.chat_model:
        payload.chat_model = settings.gemini_model_perf or "gemini-2.5-flash"

    logger.info(
        f"创建新的对话，thread_name={payload.workspace_thread_name}, chat_model={payload.chat_model}"
    )

    # 调用业务代码创建线程
    thread = await thread_service.create_thread(session, payload)
    return thread


@router.get("/threads", response_model=list[WorkspaceThreadRead])
async def list_threads(
    session: Annotated[AsyncSession, Depends(get_db)],
    thread_service: Annotated[ChatThreadService, Depends(get_chat_thread_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """
    获取工作区内的所有线程列表

    Args:
        session: 数据库会话，通过依赖注入获取
        thread_service: ChatThreadService 实例，通过依赖注入获取
        limit: 每页线程数量，默认为 10，范围 1-100
        offset: 偏移量，用于分页，默认为 0

    Returns:
        工作区内的线程列表
    """
    return await thread_service.get_threads(session, limit=limit, offset=offset)


@router.get("/thread/{thread_uid}/history", response_model=list[WorkspaceChatRead])
async def get_thread_history(
    thread_uid: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    thread_service: Annotated[ChatThreadService, Depends(get_chat_thread_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """
    获取指定线程的历史消息

    Args:
        thread_uid: 线程 UID
        session: 数据库会话，通过依赖注入获取
        thread_service: ChatThreadService 实例，通过依赖注入获取
        limit: 每页消息数量，默认为 10，范围 1-100
        offset: 偏移量，用于分页，默认为 0

    Returns:
        指定线程的历史消息列表
    """
    return await thread_service.get_thread_history(
        session, thread_uid=thread_uid, limit=limit, offset=offset
    )
