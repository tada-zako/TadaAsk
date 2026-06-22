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
from app.db.models import Project, Source
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
    """根据 AdminChatRequest 基础字段解析 ProviderWithModelInternalRead"""
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


async def _resolve_admin_sources_by_uids(
    *,
    source_uids: list[str],
    rag_search_crud: RAGSearchCRUDeps,
) -> list[Source]:
    """验证 Admin 请求中的 source_uids 是否有效，并按请求顺序返回可检索 sources"""
    rag_source_exception = HTTPException(
        status_code=400, detail="Invalid source_uids for RAG chat"
    )

    if not source_uids:
        return []

    request_source_uids = list(dict.fromkeys(source_uids))  # 去重并保持顺序
    sources = await rag_search_crud.resolve_admin_search_sources(
        source_uids=request_source_uids
    )

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


def _merge_sources(*source_groups: list[Source]) -> list[Source]:
    """按传入顺序合并 source 列表，并按 source.id 去重"""
    source_map: dict[int, Source] = {}
    for group in source_groups:
        for source in group:
            source_map.setdefault(source.id, source)
    return list(source_map.values())


def _build_admin_model_settings(
    *,
    chat_request: AdminChatRequest,
    provider_with_model: ProviderWithModelInternalRead,
) -> ModelSettings:
    """从 AdminChatRequest 基础字段提取模型参数设置"""
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
    """从 AdminRAGChatRequest 的基础聊天字段中提取模型参数设置"""
    return _build_admin_model_settings(
        chat_request=chat_request,
        provider_with_model=provider_with_model,
    )


def _build_admin_rag_plugin(
    *,
    chat_request: AdminRAGChatRequest,
    sources: list[Source],
    rag_retrieval: RAGRetrievalServiceDeps,
    provider_with_model: ProviderWithModelInternalRead,
) -> RAGChatPlugin | None:
    """根据有效的 sources 列表构建 RAGChatPlugin；无 sources 时降级为普通 chat"""
    if not sources:
        return None

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
            raise HTTPException(
                status_code=400,
                detail="The selected model does not support structured output, cannot use FULL search mode.",
            )

    return RAGChatPlugin(
        sources=sources,
        rag_retrieval=rag_retrieval,
        rag_options=rag_options,
    )


async def build_project_admin_rag_plugin(
    *,
    project: Project,
    chat_request: AdminRAGChatRequest,
    rag_search_crud: RAGSearchCRUDeps,
    rag_retrieval: RAGRetrievalServiceDeps,
    provider_with_model: ProviderWithModelInternalRead,
) -> RAGChatPlugin | None:
    """构建 project-scoped Admin RAG 插件：project sources + 额外 sources"""
    # 检索 project 关联的 sources
    project_sources = await rag_search_crud.resolve_admin_project_sources(
        project_id=project.id
    )

    # 检索携带的其它 sources
    extra_sources = await _resolve_admin_sources_by_uids(
        source_uids=chat_request.source_uids,
        rag_search_crud=rag_search_crud,
    )
    sources = _merge_sources(project_sources, extra_sources)

    return _build_admin_rag_plugin(
        chat_request=chat_request,
        sources=sources,
        rag_retrieval=rag_retrieval,
        provider_with_model=provider_with_model,
    )


async def build_global_admin_rag_plugin(
    *,
    chat_request: AdminRAGChatRequest,
    rag_search_crud: RAGSearchCRUDeps,
    rag_retrieval: RAGRetrievalServiceDeps,
    provider_with_model: ProviderWithModelInternalRead,
) -> RAGChatPlugin | None:
    """构建 global Admin RAG 插件：仅使用请求显式指定的 sources"""
    sources = await _resolve_admin_sources_by_uids(
        source_uids=chat_request.source_uids,
        rag_search_crud=rag_search_crud,
    )

    return _build_admin_rag_plugin(
        chat_request=chat_request,
        sources=sources,
        rag_retrieval=rag_retrieval,
        provider_with_model=provider_with_model,
    )


async def stream_admin_chat_events(
    *,
    project: Project | None,
    chat_request: AdminRAGChatRequest,
    completer: FullCompleter,
    provider_with_model: ProviderWithModelInternalRead,
    chat_service: ChatOrchestratorServiceDeps,
    model_settings: ModelSettings,
    rag_plugin: RAGChatPlugin | None,
) -> AsyncIterable[ServerSentEvent]:
    """Admin 端的流式对话事件生成器；复用代码"""
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
    rag_search_crud: RAGSearchCRUDeps,
    rag_retrieval: RAGRetrievalServiceDeps,
) -> AsyncIterable[ServerSentEvent]:
    """
    Project 上下文中的 Admin 流式对话;
    默认使用 project 关联的 sources 进行 RAG 检索，
    chat_session 关联到 project
    """
    rag_plugin = await build_project_admin_rag_plugin(
        project=project,
        chat_request=chat_request,
        rag_search_crud=rag_search_crud,
        rag_retrieval=rag_retrieval,
        provider_with_model=provider_with_model,
    )

    async for event in stream_admin_chat_events(
        project=project,
        chat_request=chat_request,
        completer=completer,
        provider_with_model=provider_with_model,
        chat_service=chat_service,
        model_settings=model_settings,
        rag_plugin=rag_plugin,
    ):
        yield event


@router.post("/chat/stream", response_class=EventSourceResponse)
async def stream_global_chat(
    chat_request: Annotated[AdminRAGChatRequest, Depends(get_admin_rag_chat_request)],
    completer: Annotated[FullCompleter, Depends(get_admin_rag_completer)],
    provider_with_model: Annotated[
        ProviderWithModelInternalRead, Depends(get_admin_rag_provider_with_model)
    ],
    chat_service: ChatOrchestratorServiceDeps,
    model_settings: Annotated[ModelSettings, Depends(get_rag_model_settings)],
    rag_search_crud: RAGSearchCRUDeps,
    rag_retrieval: RAGRetrievalServiceDeps,
) -> AsyncIterable[ServerSentEvent]:
    """
    Global 上下文的 Admin 流式对话；
    仅使用请求体中显式指定的 sources 进行 RAG 检索，
    chat_session 不关联 project
    """
    rag_plugin = await build_global_admin_rag_plugin(
        chat_request=chat_request,
        rag_search_crud=rag_search_crud,
        rag_retrieval=rag_retrieval,
        provider_with_model=provider_with_model,
    )

    async for event in stream_admin_chat_events(
        project=None,
        chat_request=chat_request,
        completer=completer,
        provider_with_model=provider_with_model,
        chat_service=chat_service,
        model_settings=model_settings,
        rag_plugin=rag_plugin,
    ):
        yield event
