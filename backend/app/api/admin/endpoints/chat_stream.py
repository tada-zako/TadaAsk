from typing import Annotated, AsyncIterable

from fastapi import APIRouter, Body, Depends, HTTPException, Path
from fastapi.sse import EventSourceResponse, ServerSentEvent

from ...deps import (
    APIKeyCipherDeps,
    ChatOrchestratorServiceDeps,
    RAGRetrievalServiceDeps,
    SessionFactoryDeps,
)
from ...schemas import AdminRAGChatRequest
from app.crud import ModelProfileCRUD, ProjectCRUD, RAGSearchCRUD
from app.db.models import Project, Source
from app.db.schemas import HybridSearchOptions, ProviderWithModelInternalRead
from app.providers import FullCompleter, ModelSettings, completer_factory
from app.services.chat import ChatInput, ChatOrchestratorService, RAGChatPlugin
from app.services.search import RAGRetrievalService
from app.core.constants import ChatSessionType, SearchMode


router = APIRouter()


async def get_admin_rag_chat_request(
    chat_request: Annotated[
        AdminRAGChatRequest, Body(..., description="AdminRAGChatRequest 请求体")
    ],
) -> AdminRAGChatRequest:
    """从请求体中解析 AdminRAGChatRequest 对象，作为依赖注入接口。"""
    return chat_request


async def valid_stream_project(
    session_factory: SessionFactoryDeps,
    project_uid: Annotated[str, Path(..., description="Project UID")],
) -> Project:
    """Admin stream 专用 project 校验；短事务查询后返回已加载 settings 的项目。"""
    async with session_factory() as session:
        project_crud = ProjectCRUD(session=session)
        project = await project_crud.get_project_with_settings_by_uid(
            project_uid=project_uid
        )

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return project


async def get_admin_rag_provider_with_model(
    chat_request: Annotated[AdminRAGChatRequest, Depends(get_admin_rag_chat_request)],
    session_factory: SessionFactoryDeps,
    api_key_cipher: APIKeyCipherDeps,
) -> ProviderWithModelInternalRead:
    """Admin stream 专用模型配置解析；避免 request scope DB session 进入 SSE。"""
    async with session_factory() as session:
        model_profile_crud = ModelProfileCRUD(session=session)
        provider_with_model = (
            await model_profile_crud.get_internal_provider_with_model_profile_by_uid(
                provider_uid=chat_request.provider_uid,
                model_uid=chat_request.model_uid,
                api_key_cipher=api_key_cipher,
            )
        )

    if not provider_with_model:
        raise HTTPException(status_code=400, detail="Invalid provider_uid or model_uid")

    return provider_with_model


async def get_admin_rag_completer(
    provider_with_model: Annotated[
        ProviderWithModelInternalRead, Depends(get_admin_rag_provider_with_model)
    ],
) -> FullCompleter:
    """根据 AdminRAGChatRequest 请求体获取对应的 FullCompleter 实例。"""
    return completer_factory(provider_with_model=provider_with_model)


def _build_admin_model_settings(
    *,
    chat_request: AdminRAGChatRequest,
    provider_with_model: ProviderWithModelInternalRead,
) -> ModelSettings:
    """从 AdminRAGChatRequest 基础字段提取模型参数设置。"""
    return ModelSettings.for_admin_chat(
        profile=provider_with_model.model_profile,
        request=chat_request,
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


async def _resolve_admin_sources_by_uids(
    *,
    source_uids: list[str],
    rag_search_crud: RAGSearchCRUD,
) -> list[Source]:
    """验证 Admin 请求中的 source_uids 是否有效，并按请求顺序返回可检索 sources。"""
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
        raise HTTPException(status_code=400, detail="Invalid source_uids for RAG chat")

    return [source_uid_map_source[uid] for uid in request_source_uids]


def _merge_sources(*source_groups: list[Source]) -> list[Source]:
    """按传入顺序合并 source 列表，并按 source.id 去重。"""
    source_map: dict[int, Source] = {}
    for group in source_groups:
        for source in group:
            source_map.setdefault(source.id, source)
    return list(source_map.values())


def _build_admin_rag_plugin(
    *,
    chat_request: AdminRAGChatRequest,
    sources: list[Source],
    rag_retrieval: RAGRetrievalService,
    provider_with_model: ProviderWithModelInternalRead,
) -> RAGChatPlugin | None:
    """根据有效的 sources 列表构建 RAGChatPlugin；无 sources 时降级为普通 chat。"""
    if not sources:
        return None

    rag_options = HybridSearchOptions.model_validate(
        chat_request.rag_options.model_dump()
    )

    # 如果 model 不支持 structured：
    if not provider_with_model.model_profile.supports_structured:
        # - standalone rewriter 自动降级
        if rag_options.standalone_enabled:
            rag_options.standalone_enabled = False

        # - SearchMode.ADAPTIVE 降级为 SearchMode.FAST
        if rag_options.mode == SearchMode.ADAPTIVE:
            rag_options.mode = SearchMode.FAST
        # - SearchMode.FULL 模式报错
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


async def get_project_admin_rag_plugin(
    project: Annotated[Project, Depends(valid_stream_project)],
    chat_request: Annotated[AdminRAGChatRequest, Depends(get_admin_rag_chat_request)],
    session_factory: SessionFactoryDeps,
    rag_retrieval: RAGRetrievalServiceDeps,
    provider_with_model: Annotated[
        ProviderWithModelInternalRead, Depends(get_admin_rag_provider_with_model)
    ],
) -> RAGChatPlugin | None:
    """构建 project-scoped Admin RAG 插件；所有 DB 查询在短 session 内完成。"""
    async with session_factory() as session:
        rag_search_crud = RAGSearchCRUD(session=session)
        project_sources = await rag_search_crud.resolve_admin_project_sources(
            project_id=project.id
        )
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


async def get_global_admin_rag_plugin(
    chat_request: Annotated[AdminRAGChatRequest, Depends(get_admin_rag_chat_request)],
    session_factory: SessionFactoryDeps,
    rag_retrieval: RAGRetrievalServiceDeps,
    provider_with_model: Annotated[
        ProviderWithModelInternalRead, Depends(get_admin_rag_provider_with_model)
    ],
) -> RAGChatPlugin | None:
    """构建 global Admin RAG 插件；仅使用请求显式指定的 sources。"""
    async with session_factory() as session:
        rag_search_crud = RAGSearchCRUD(session=session)
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
    chat_service: ChatOrchestratorService,
    model_settings: ModelSettings,
    rag_plugin: RAGChatPlugin | None,
) -> AsyncIterable[ServerSentEvent]:
    """Admin 端的流式对话事件生成器；复用代码。"""
    async for event in chat_service.stream_rag_chat(
        project=project,
        chat_input=ChatInput(
            message=chat_request.message,
            chat_session_uid=chat_request.chat_session_uid,
            admin_system_prompt=chat_request.admin_system_prompt,
        ),
        completer=completer,
        provider_with_model=provider_with_model,
        requester_type=ChatSessionType.ADMIN,
        model_settings=model_settings,
        rag_plugin=rag_plugin,
    ):
        yield ServerSentEvent(
            event=event.event,
            data=event.model_dump(
                exclude={"event"},
                by_alias=True,
                mode="json",
            ),
        )


@router.post("/project/{project_uid}/chat/stream", response_class=EventSourceResponse)
async def stream_chat(
    chat_request: Annotated[AdminRAGChatRequest, Depends(get_admin_rag_chat_request)],
    project: Annotated[Project, Depends(valid_stream_project)],
    completer: Annotated[FullCompleter, Depends(get_admin_rag_completer)],
    provider_with_model: Annotated[
        ProviderWithModelInternalRead, Depends(get_admin_rag_provider_with_model)
    ],
    chat_service: ChatOrchestratorServiceDeps,
    model_settings: Annotated[ModelSettings, Depends(get_rag_model_settings)],
    rag_plugin: Annotated[RAGChatPlugin | None, Depends(get_project_admin_rag_plugin)],
) -> AsyncIterable[ServerSentEvent]:
    """
    Project 上下文中的 Admin 流式对话；
    默认使用 project 关联的 sources 进行 RAG 检索，chat_session 关联到 project。
    """
    # TODO: 考虑到前端 ask view 不是 MVP 阶段业务，暂时不具体修改内部逻辑
    # 后续为区分 ask/chat 业务范围，可能需要考虑限制 ask 的相关配置设计，
    # 例如统一通过 project settings 读取设置，并限制模型能力等——以模拟 visitor 请求性能
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
    rag_plugin: Annotated[RAGChatPlugin | None, Depends(get_global_admin_rag_plugin)],
) -> AsyncIterable[ServerSentEvent]:
    """
    Global 上下文的 Admin 流式对话；
    仅使用请求体中显式指定的 sources 进行 RAG 检索，chat_session 不关联 project。
    """
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
