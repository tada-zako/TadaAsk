from typing import AsyncIterable, Annotated, Any

from fastapi import APIRouter, Body, Depends
from loguru import logger

from ...schemas import ChatRequest
from ...deps import (
    SessionDeps,
    ValidProjectDeps,
    RAGServiceDeps,
    ChatMessageCRUDeps,
    ChatSessionCRUDeps,
)
from app.core.config import settings
from app.core.constants import ChatSessionType
from app.db.models import ChatSession
from app.db.schemas import ChatSessionInternal
from app.providers import Model, model_factory
from app.services import ChatService


router = APIRouter()


def get_visitor_model(
    project: ValidProjectDeps,
) -> Model[Any]:
    """
    游客级 model 工厂: 基于关联的 Project 获取对应的 Model 实例。
    NOTE: 目前仅支持 GeminiModel。
    """
    provider_name = project.provider or settings.llm_provider_visitor or "deepseek"
    # TODO: 模型字段的获取逻辑，后期重新处理；
    model_name = project.model or settings.gemini_model_perf or None
    return model_factory(provider=provider_name, model=model_name)


ModelDeps = Annotated[Model[Any], Depends(get_visitor_model)]


async def valid_or_create_visitor_chat_session(
    chat_session_crud: ChatSessionCRUDeps,
    model: ModelDeps,
    project: ValidProjectDeps,
    visitor_id: Annotated[
        str | None,
        Body(
            default=None,
            alias="visitorId",
            description="访客 ID: 针对匿名用户可选字段，便于后续分析和调试",
        ),
    ] = None,
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
            # 检查会话类型是否为 VISITOR，如果不是则抛出异常
            if chat_session.session_type != ChatSessionType.VISITOR:
                logger.warning(
                    f"Chat session {chat_session_uid} is not a visitor session, creating new chat session"
                )
                raise ValueError(
                    "Invalid chat_session_uid for visitor session, creating new chat session"
                )

            return chat_session
        else:
            logger.warning(
                f"Invalid chat_session_uid: {chat_session_uid}, creating new chat session"
            )
            raise ValueError("Invalid chat_session_uid, creating new chat session")

    # 如果没有提供有效的 chat_session_uid，则创建新的聊天会话
    new_chat_session = await chat_session_crud.create_chat_session(
        chat_session_data=ChatSessionInternal(
            chat_session_name="New Chat Session",
            model=model.model_name,
            visitor_id=visitor_id,
            session_type=ChatSessionType.VISITOR,
            project_id=project.id,
        ),
    )
    return new_chat_session


def get_visitor_chat_service(
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


@router.post("/project/{project_uid}/chat/stream")
async def stream_chat(
    chat_request: ChatRequest,
    project: ValidProjectDeps,
    chat_session: Annotated[ChatSession, Depends(valid_or_create_visitor_chat_session)],
    chat_service: Annotated[ChatService, Depends(get_visitor_chat_service)],
) -> AsyncIterable[str]:
    """
    流式调用 LLM 生成聊天回复（无 Agent）

    Args:
        chat_request: 前端传递的聊天请求数据，包含用户消息和相关参数
        project: 通过依赖注入获取的项目实例，基于 project_uid 验证
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
