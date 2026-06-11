from typing import AsyncIterable, Annotated, Any

from fastapi import APIRouter, Body, Depends
from fastapi.sse import EventSourceResponse, ServerSentEvent
from loguru import logger

from ...schemas import ChatRequest
from ...deps import (
    SessionDeps,
    ValidProjectDeps,
    ChatSessionCRUDeps,
    ChatMessageCRUDeps,
    ModelProfileCRUDeps,
)
from app.providers import TextCompleter, completer_factory
from app.db.models import ChatSession
from app.db.schemas import ChatSessionInternal
from app.services import ChatService
from app.core.config import settings
from app.core.constants import ChatSessionType


router = APIRouter()


async def get_admin_model(
    model_profile_crud: ModelProfileCRUDeps,
    model_profile_uid: Annotated[
        str,
        Body(
            embed=True,
            alias="modelProfileUid",
            description="前端传递的 model_profile_uid；禁止为空",
        ),
    ],
) -> TextCompleter:
    """依赖注入接口：根据前端传递的 model_profile_uid 获取对应的 TextCompleter 实例"""
    model_profile = await model_profile_crud.get_enabled_model_profile_by_uid(
        profile_uid=model_profile_uid
    )
    if not model_profile:
        logger.error(f"Invalid model_profile_uid: {model_profile_uid}")
        raise ValueError("Invalid model_profile_uid")

    completer = completer_factory(
        provider=model_profile.provider,
        model=model_profile.model,
    )
    return completer


ModelDeps = Annotated[TextCompleter, Depends(get_admin_model)]


async def valid_or_create_admin_chat_session(
    chat_session_crud: ChatSessionCRUDeps,
    model: ModelDeps,
    project: ValidProjectDeps,
    chat_session_uid: Annotated[
        str | None,
        Body(
            embed=True,
            alias="chatSessionUid",
            description="前端传递的 chat_session_uid, 为空时创建新的对话",
        ),
    ] = None,
) -> ChatSession:
    """
    Admin 端 ChatSession 依赖：
    验证 chat_session_uid 是否有效，返回对应的 ChatSession 实例。
    如果 chat_session_uid 为空或无效，则创建新的 ChatSession 实例并返回。
    """
    if chat_session_uid:
        chat_session = await chat_session_crud.get_chat_session_by_uid(
            chat_session_uid=chat_session_uid
        )
        if chat_session:
            return chat_session
        else:
            logger.warning(
                f"Invalid chat_session_uid: {chat_session_uid}, creating new chat session"
            )
            raise ValueError("Invalid chat_session_uid, creating new chat session")

    # 如果没有提供有效的 chat_session_uid，则创建新的聊天会话
    new_chat_session = await chat_session_crud.create_chat_session(
        chat_session_data=ChatSessionInternal(
            title="New Chat Session",
            model=model.model_name,
            session_type=ChatSessionType.ADMIN,
            project_id=project.id,
        ),
    )
    return new_chat_session


def get_admin_chat_service(
    session: SessionDeps,
    chat_message_crud: ChatMessageCRUDeps,
    llm_model: ModelDeps,
    rag_service: RAGServiceDeps,
) -> ChatService:
    """聊天服务工厂函数，提供 ChatService 实例"""
    return ChatService(
        session,
        chat_message_crud=chat_message_crud,
        llm_model=llm_model,
        rag_service=rag_service,
    )


# TODO: 后续改成使用 EventSourceResponse，支持 SSE 协议
# TODO: opencode 设计：每个 new session 都会在上下文顶部插入一条“自动聊天会话标签生成”的要求
@router.post("/project/{project_uid}/chat/stream", response_model=EventSourceResponse)
async def stream_chat(
    chat_request: ChatRequest,
    project: ValidProjectDeps,
    chat_session: Annotated[ChatSession, Depends(valid_or_create_admin_chat_session)],
    chat_service: Annotated[ChatService, Depends(get_admin_chat_service)],
) -> AsyncIterable[ServerSentEvent]:
    """
    流式调用 LLM 生成聊天回复（无 Agent）

    Args:
        chat_request: 前端传递的聊天请求数据，包含用户消息和相关参数
        project: 通过依赖注入获取的项目实例，用于 project_uid 验证
        chat_session: 通过依赖注入获取或创建的聊天会话实例，基于 chat_session_uid 验证或创建
        chat_service: 通过依赖注入获取的 ChatService 实例，用于处理聊天逻辑

    Returns:
        异步生成的聊天回复字符串流
    """
    logger.info(
        f"Received chat request: {chat_request} for project {project.id} and chat session {chat_session.uid}"
    )

    async with chat_service.stream_chat_reply(
        project=project,
        chat_session=chat_session,
        user_message=chat_request.message,
        top_k=chat_request.doc_top_k,
    ) as chat_result:
        # 开启异步上下文，迭代异步生成器输出结果
        async for chunk in chat_result.stream_reply():
            yield chunk
