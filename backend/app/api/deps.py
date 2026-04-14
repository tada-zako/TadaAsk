from typing import Annotated, Any

from fastapi import Depends, Body, HTTPException, Path
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession


from .schemas import TokenData
from app.db import get_db
from app.db.models import Admins, Projects, ChatSessions
from app.db.schemas import ChatSessionCreate
from app.crud import project_crud, chat_session_crud, admin_crud
from app.core.constants import ChatSessionType
from app.core.security import decode_access_token
from app.rag import VectorDatabase, vector_db_factory
from app.providers import Model, model_factory
from app.services import RAGService, ChatService


def get_model(
    provider_name: Annotated[str | None, Body(embed=True, alias="providerName")] = None,
    model_name: Annotated[str | None, Body(embed=True, alias="modelName")] = None,
) -> Model[Any]:
    """
    model 工厂，根据 provider_name 返回对应的 Model 实例。
    NOTE: 目前仅支持 GeminiModel。
    """
    return model_factory(provider=provider_name, model=model_name)


def get_vector_db(
    vector_store_name: Annotated[
        str | None, Body(embed=True, alias="vectorStoreName")
    ] = None,
) -> VectorDatabase:
    """
    向量库工厂函数，根据配置返回对应的 VectorDatabase 实例。
    NOTE: 目前仅支持 ChromaDB。
    """

    return vector_db_factory(vector_store=vector_store_name)


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_current_admin(
    session: "SessionDeps",
    token: Annotated[str, Depends(oauth2_scheme)],
) -> Admins:
    """获取当前登录的管理员实例，基于 JWT 令牌进行鉴权"""
    credentials_exception = HTTPException(
        status_code=401, detail="Invalid authentication credentials"
    )

    payload = decode_access_token(token)
    if not payload:
        raise credentials_exception

    token_data = TokenData.model_validate(payload)
    if not token_data.username:
        raise credentials_exception

    admin = await admin_crud.get_admin_by_username(
        session, username=token_data.username
    )
    if not admin or admin.token_version != token_data.token_version:
        raise credentials_exception
    return admin


async def valid_project(
    project_uid: Annotated[str, Path(..., description="Project UID")],
    session: "SessionDeps",
) -> Projects:
    """验证项目 UID 是否有效，返回项目实例或抛出 HTTPException"""
    project = await project_crud.get_project_by_uid(
        session=session, project_uid=project_uid
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def valid_or_create_chat_session(
    session: "SessionDeps",
    model: "ModelDeps",
    project: "ValidProjectDeps",
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
            description="前端传递的 chat_session_uid: 为空时创建新的对话",
        ),
    ] = None,
) -> ChatSessions:
    """
    验证 chat_session_uid 是否有效，返回对应的 ChatSessions 实例。
    如果 chat_session_uid 为空或无效，则创建新的 ChatSessions 实例并返回。
    """
    if chat_session_uid:
        chat_session = await chat_session_crud.get_chat_session_by_uid(
            session=session, chat_session_uid=chat_session_uid
        )
        if chat_session:
            return chat_session

    # TODO: 这里还是需要基于鉴权方式的实现来确定会话的创建逻辑
    # 如果没有提供有效的 chat_session_uid，则创建新的聊天会话
    new_chat_session = await chat_session_crud.create_chat_session(
        session,
        chat_session_data=ChatSessionCreate(
            chat_session_name="New Chat Session",
            model=model.model_name,
            session_type=ChatSessionType.ADMIN,
            project_id=project.id,
        ),
    )
    return new_chat_session


def get_rag_service(session: "SessionDeps", vector_db: "VectorDBDeps") -> RAGService:
    """依赖注入接口：提供 RAGService 实例"""
    return RAGService(session=session, vector_db=vector_db)


def get_chat_service(
    session: "SessionDeps",
    llm_model: "ModelDeps",
    rag_service: "RAGServiceDeps",
) -> ChatService:
    """聊天服务工厂函数，提供 ChatService 实例"""
    return ChatService(
        session,
        llm_model=llm_model,
        rag_service=rag_service,
    )


# 数据库会话依赖
SessionDeps = Annotated[AsyncSession, Depends(get_db)]
# LLM 模型依赖
ModelDeps = Annotated[Model[Any], Depends(get_model)]
# 向量库依赖
VectorDBDeps = Annotated[VectorDatabase, Depends(get_vector_db)]
# valid project 依赖
ValidProjectDeps = Annotated[Projects, Depends(valid_project)]
# chat session 依赖
ValidChatSessionDeps = Annotated[ChatSessions, Depends(valid_or_create_chat_session)]
# RAG 服务依赖
RAGServiceDeps = Annotated[RAGService, Depends(get_rag_service)]
# 聊天服务依赖
ChatServiceDeps = Annotated[ChatService, Depends(get_chat_service)]
