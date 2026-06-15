from typing import AsyncIterable, Annotated

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.sse import EventSourceResponse, ServerSentEvent
from loguru import logger

from ...deps import (
    APIKeyCipherDeps,
    ValidProjectDeps,
    ModelProfileCRUDeps,
    RAGSearchCRUDeps,
    ChatOrchestratorServiceDeps,
    RAGRetrievalServiceDeps,
)
from ...schemas import AdminRAGChatRequest, AdminChatRequest
from app.providers import FullCompleter, completer_factory, ModelSettings
from app.services.chat import ChatInput, RAGChatPlugin
from app.db.models import Source
from app.db.schemas import HybridSearchOptions, ProviderWithModelInternalRead
from app.core.constants import ChatSessionType, SearchMode


router = APIRouter()


async def get_admin_chat_request(
    chat_request: Annotated[
        AdminChatRequest, Body(..., description="AdminChatRequest 请求体")
    ],
) -> AdminChatRequest:
    """从请求体中解析 AdminChatRequest 对象，作为依赖注入接口"""
    return chat_request


async def get_admin_rag_chat_request(
    chat_request: Annotated[
        AdminRAGChatRequest, Body(..., description="AdminRAGChatRequest 请求体")
    ],
) -> AdminRAGChatRequest:
    """从请求体中解析 AdminRAGChatRequest 对象，作为依赖注入接口"""
    return chat_request


async def _resolve_admin_provider_with_model(
    *,
    chat_request: AdminChatRequest,
    model_profile_crud: ModelProfileCRUDeps,
    api_key_cipher: APIKeyCipherDeps,
) -> ProviderWithModelInternalRead:
    """根据 AdminChatRequest 基础字段解析 ProviderWithModelInternalRead。"""
    provider_with_model = (
        await model_profile_crud.get_internal_provider_with_model_profile_by_uid(
            provider_uid=chat_request.provider_uid,
            model_uid=chat_request.model_uid,
            api_key_cipher=api_key_cipher,
        )
    )

    if not provider_with_model:
        logger.error(
            f"Invalid provider_uid or model_uid: {chat_request.provider_uid}, {chat_request.model_uid}"
        )
        raise ValueError("Invalid provider_uid or model_uid")

    return provider_with_model


async def get_admin_provider_with_model(
    chat_request: Annotated[AdminChatRequest, Depends(get_admin_chat_request)],
    model_profile_crud: ModelProfileCRUDeps,
    api_key_cipher: APIKeyCipherDeps,
) -> ProviderWithModelInternalRead:
    """依赖注入接口：根据前端传递的 provider_uid 和 model_uid 获取对应的 ProviderWithModelInternalRead 实例"""
    return await _resolve_admin_provider_with_model(
        chat_request=chat_request,
        model_profile_crud=model_profile_crud,
        api_key_cipher=api_key_cipher,
    )


async def get_admin_rag_provider_with_model(
    chat_request: Annotated[AdminRAGChatRequest, Depends(get_admin_rag_chat_request)],
    model_profile_crud: ModelProfileCRUDeps,
    api_key_cipher: APIKeyCipherDeps,
) -> ProviderWithModelInternalRead:
    """依赖注入接口：RAG 请求复用 AdminChatRequest 基础字段解析模型配置"""
    return await _resolve_admin_provider_with_model(
        chat_request=chat_request,
        model_profile_crud=model_profile_crud,
        api_key_cipher=api_key_cipher,
    )


async def get_admin_completer(
    provider_with_model: Annotated[
        ProviderWithModelInternalRead, Depends(get_admin_provider_with_model)
    ],
) -> FullCompleter:
    """依赖注入接口：根据 AdminChatRequest 请求体获取对应的 FullCompleter 实例"""
    return completer_factory(provider_with_model=provider_with_model)


async def get_admin_rag_completer(
    provider_with_model: Annotated[
        ProviderWithModelInternalRead, Depends(get_admin_rag_provider_with_model)
    ],
) -> FullCompleter:
    """依赖注入接口：根据 AdminRAGChatRequest 请求体获取对应的 FullCompleter 实例"""
    return completer_factory(provider_with_model=provider_with_model)


async def valid_sources(
    chat_request: Annotated[AdminRAGChatRequest, Depends(get_admin_rag_chat_request)],
    rag_search_crud: RAGSearchCRUDeps,
) -> list[Source]:
    """依赖注入接口：验证 AdminChatRequest 中的 source_uids 是否有效，返回有效的 source_uids 列表或 None"""
    rag_source_exception = HTTPException(
        status_code=400, detail="Invalid source_uids for RAG chat"
    )

    if not chat_request.source_uids:
        raise rag_source_exception

    request_source_uids = list(
        dict.fromkeys(chat_request.source_uids)
    )  # 去重并保持顺序
    sources = await rag_search_crud.resolve_admin_search_sources(
        source_uids=request_source_uids
    )
    if not sources:
        raise rag_source_exception

    source_uid_map_source = {source.uid: source for source in sources}
    missing_source = [
        uid for uid in request_source_uids if uid not in source_uid_map_source
    ]
    if missing_source:
        logger.error(
            f"Invalid source_uids for RAG chat, missing source_uids: {missing_source}"
        )
        raise rag_source_exception

    return [source_uid_map_source[uid] for uid in request_source_uids]


def _build_admin_model_settings(
    *,
    chat_request: AdminChatRequest,
    provider_with_model: ProviderWithModelInternalRead,
) -> ModelSettings:
    """从 AdminChatRequest 基础字段提取模型参数设置。"""
    return ModelSettings.for_admin_chat(
        profile=provider_with_model.model_profile,
        request=chat_request,
    )


async def get_model_settings(
    chat_request: Annotated[AdminChatRequest, Depends(get_admin_chat_request)],
    provider_with_model: Annotated[
        ProviderWithModelInternalRead, Depends(get_admin_provider_with_model)
    ],
) -> ModelSettings:
    """从 AdminChatRequest 请求体中提取模型参数设置，返回 ModelSettings 实例"""
    return _build_admin_model_settings(
        chat_request=chat_request,
        provider_with_model=provider_with_model,
    )


async def get_rag_model_settings(
    chat_request: Annotated[AdminRAGChatRequest, Depends(get_admin_rag_chat_request)],
    provider_with_model: Annotated[
        ProviderWithModelInternalRead, Depends(get_admin_rag_provider_with_model)
    ],
) -> ModelSettings:
    """从 AdminRAGChatRequest 的基础聊天字段中提取模型参数设置。"""
    return _build_admin_model_settings(
        chat_request=chat_request,
        provider_with_model=provider_with_model,
    )


async def get_rag_plugin(
    chat_request: Annotated[AdminRAGChatRequest, Depends(get_admin_rag_chat_request)],
    sources: Annotated[list[Source], Depends(valid_sources)],
    rag_retrieval: RAGRetrievalServiceDeps,
    provider_with_model: Annotated[
        ProviderWithModelInternalRead, Depends(get_admin_rag_provider_with_model)
    ],
) -> RAGChatPlugin:
    """依赖注入接口：根据有效的 sources 列表构建 RAGChatPlugin 实例"""
    # 0. Options 策略检查和调整
    # 如果 model 不支持 structured：
    # - standalone rewriter 自动降级
    # - SearchMode.ADAPTIVE 降级为 SearchMode.FAST
    # - SearchMode.FULL 模式报错
    rag_options = HybridSearchOptions.model_validate(
        chat_request.rag_options.model_dump()
    )

    if not provider_with_model.model_profile.supports_structured:
        if rag_options.standalone_enabled:
            rag_options.standalone_enabled = False

        if rag_options.mode == SearchMode.ADAPTIVE:
            rag_options.mode = SearchMode.FAST
        elif rag_options.mode == SearchMode.FULL:
            raise ValueError(
                "The selected model does not support structured output, cannot use FULL search mode."
            )

    return RAGChatPlugin(
        sources=sources,
        rag_retrieval=rag_retrieval,
        rag_options=rag_options,
    )


# TODO: opencode 设计：每个 new session 都会在上下文顶部插入一条“自动聊天会话标签生成”的要求
@router.post("/project/{project_uid}/chat/stream", response_class=EventSourceResponse)
async def stream_chat(
    chat_request: Annotated[AdminRAGChatRequest, Depends(get_admin_rag_chat_request)],
    project: ValidProjectDeps,
    completer: Annotated[FullCompleter, Depends(get_admin_rag_completer)],
    provider_with_model: Annotated[
        ProviderWithModelInternalRead, Depends(get_admin_rag_provider_with_model)
    ],
    chat_service: ChatOrchestratorServiceDeps,
    model_settings: Annotated[ModelSettings, Depends(get_rag_model_settings)],
    rag_plugin: Annotated[RAGChatPlugin, Depends(get_rag_plugin)],
) -> AsyncIterable[ServerSentEvent]:
    """
    流式调用 LLM 生成聊天回复（无 Agent）
    """
    async for event in chat_service.stream_rag_chat(
        project=project,
        chat_input=ChatInput(
            message=chat_request.message,
            chat_session_uid=chat_request.chat_session_uid,
        ),
        completer=completer,
        provider_with_model=provider_with_model,
        requester_type=ChatSessionType.ADMIN,
        model_settings=model_settings,
        rag_plugin=rag_plugin,
    ):
        yield ServerSentEvent(
            event=event.event,
            data=event.model_dump_json(
                exclude={"event"},
                by_alias=True,
            ),
        )
