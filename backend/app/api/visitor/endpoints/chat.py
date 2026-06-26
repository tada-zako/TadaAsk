from typing import AsyncIterable, Annotated, cast, AsyncIterator

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Request
from fastapi.sse import ServerSentEvent, EventSourceResponse
from loguru import logger

from ...deps import (
    VisitorRateLimiterDeps,
    APIKeyCipherDeps,
    ClientIPDeps,
    ValidVisitorChatProjectDeps,
    ProjectCRUDeps,
    RAGSearchCRUDeps,
    ChatOrchestratorServiceDeps,
    RAGRetrievalServiceDeps,
    GenerationRegistryDeps,
)
from ...schemas import VisitorChatRequest, VisitorChatCancelResponse
from app.services.chat import ChatInput, RAGChatPlugin
from app.providers import FullCompleter, completer_factory, ModelSettings
from app.db.models import Provider, ModelProfile, ProjectWidget
from app.db.schemas import (
    HybridSearchOptions,
    ProviderWithModelInternalRead,
    ProviderRead,
    ModelProfileRead,
)
from app.core.config import settings
from app.core.exceptions import VisitorRateLimitError
from app.core.rate_limit import VisitorStreamLease
from app.core.constants import ChatSessionType, SearchMode
from app.utils import normalize_origin


router = APIRouter()


async def get_visitor_chat_request(
    chat_request: Annotated[
        VisitorChatRequest, Body(..., description="VisitorChatRequest 请求体")
    ],
) -> VisitorChatRequest:
    """从请求体中解析 VisitorChatRequest 对象，作为依赖注入接口"""
    return chat_request


async def valid_visitor_widget(
    request: Request,
    project: ValidVisitorChatProjectDeps,
    project_crud: ProjectCRUDeps,
    widget_uid: Annotated[str, Path(..., description="Widget UID")],
) -> ProjectWidget:
    """验证 visitor 请求中的 widget 是否属于 project 且允许当前 Origin"""
    widget = await project_crud.get_project_widget_by_uid(
        project_id=project.id,
        widget_uid=widget_uid,
    )
    if not widget:
        raise HTTPException(status_code=404, detail="Project widget not found")

    if not widget.is_enabled:
        # 判断 widget 是否启用
        raise HTTPException(status_code=403, detail="Project widget is disabled")

    # 额外检查 origin 是否匹配 widget 的 site_origin
    # NOTE: 关于 Depends 中的 origin 检查是否必要，后续再分析
    # 这里的检查逻辑可能是不必要的
    origin = request.headers.get("origin")
    if not origin:
        raise HTTPException(status_code=403, detail="Origin header is required")

    try:
        if not normalize_origin(origin) == widget.site_origin:
            raise HTTPException(
                status_code=403,
                detail="Origin is not allowed for this widget",
            )
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Invalid Origin header") from exc

    return widget


async def get_visitor_provider_with_model(
    project: ValidVisitorChatProjectDeps,
    api_key_cipher: APIKeyCipherDeps,
) -> ProviderWithModelInternalRead:
    """
    Visitor: 从 Project 实例中装配 ProviderWithModelInternalRead 实例
    """
    settings = project.project_settings

    provider = cast(Provider, settings.visitor_default_provider)
    model_profile = cast(ModelProfile, settings.visitor_default_model_profile)

    # 1. 解密 API Key
    decrypted_api_key = None
    if provider.encrypted_api_key:
        decrypted_api_key = api_key_cipher.decrypt(provider.encrypted_api_key)

    # 2. 将 ORM 数据转为 Pydantic 读取模型
    provider_dict = ProviderRead.model_validate(provider).model_dump()
    provider_dict["api_key"] = decrypted_api_key
    provider_dict["model_profile"] = ModelProfileRead.model_validate(model_profile)

    # 3. 创建 Pydantic 内部实例
    return ProviderWithModelInternalRead.model_validate(provider_dict)


async def get_visitor_completer(
    provider_with_model: Annotated[
        ProviderWithModelInternalRead, Depends(get_visitor_provider_with_model)
    ],
) -> FullCompleter:
    """Visitor: 基于 ProviderWithModelInternalRead 实例构建 FullCompleter 实例"""
    return completer_factory(provider_with_model=provider_with_model)


async def get_visitor_model_settings(
    project: ValidVisitorChatProjectDeps,
    provider_with_model: Annotated[
        ProviderWithModelInternalRead, Depends(get_visitor_provider_with_model)
    ],
) -> ModelSettings:
    """Visitor: 从 ProviderWithModelInternalRead 实例创建 ModelSettings 实例"""
    return ModelSettings.for_visitor_chat(
        project_settings=project.project_settings,
        profile=provider_with_model.model_profile,
    )


async def get_rag_plugin(
    project: ValidVisitorChatProjectDeps,
    rag_search_crud: RAGSearchCRUDeps,
    rag_retrieval: RAGRetrievalServiceDeps,
    provider_with_model: Annotated[
        ProviderWithModelInternalRead, Depends(get_visitor_provider_with_model)
    ],
) -> RAGChatPlugin | None:
    """根据项目配置动态生成 RAGChatPlugin"""
    settings = project.project_settings
    if not settings.visitor_rag_enabled:
        logger.info(f"Project {project.uid} RAG plugin not enabled for visitor chat")
        return None

    # Options 策略检查和调整
    # 如果 model 不支持 structured：
    # - standalone rewriter 自动降级
    # - SearchMode.ADAPTIVE 降级为 SearchMode.FAST
    # - SearchMode.FULL 模式报错
    rag_options = HybridSearchOptions(
        mode=settings.rag_mode,
        top_k=settings.rag_top_k,
        rerank_enabled=settings.rag_rerank_enabled,
        fts_k=settings.rag_fts_k,
        vector_k=settings.rag_vector_k,
        rerank_k=settings.rag_rerank_k,
        max_alternative_queries=settings.rag_max_alternative_queries,
        max_keywords=settings.rag_max_keywords,
        standalone_enabled=settings.rag_standalone_enabled,
    )

    if not provider_with_model.model_profile.supports_structured:
        if rag_options.standalone_enabled:
            rag_options.standalone_enabled = False

        if rag_options.mode == SearchMode.ADAPTIVE:
            rag_options.mode = SearchMode.FAST
        elif rag_options.mode == SearchMode.FULL:
            raise HTTPException(
                status_code=400,
                detail="Model does not support structured output, cannot use FULL search mode",
            )

    sources = await rag_search_crud.resolve_visitor_search_sources(
        project_id=project.id
    )
    if not sources:
        raise HTTPException(
            status_code=400, detail="No valid sources found for RAG chat"
        )

    return RAGChatPlugin(
        rag_retrieval=rag_retrieval,
        sources=sources,
        rag_options=rag_options,
    )


async def enforce_visitor_project_rate_limit(
    visitor_rate_limiter: VisitorRateLimiterDeps,
    client_ip: ClientIPDeps,
    project_uid: Annotated[str, Path(..., description="Project UID")],
) -> None:
    """强制执行 Visitor 侧的通用 project 请求限流策略"""
    try:
        await visitor_rate_limiter.check_request(ip=client_ip, project_uid=project_uid)
    except VisitorRateLimitError as exc:
        # 直接上抛，交给全局异常处理器处理
        raise exc


async def enforce_visitor_chat_rate_limit(
    chat_request: Annotated[VisitorChatRequest, Depends(get_visitor_chat_request)],
    _rate_limit: Annotated[None, Depends(enforce_visitor_project_rate_limit)],
) -> None:
    """
    强制执行 Visitor 侧的请求限流策略
    NOTE: 这里单独将消息长度限制逻辑提取到依赖函数，
    是因为 fastapi 进入 stream_chat() 中时，此时已经开始 SSE 流程；
    如果将消息限制逻辑放到 API 函数体中，异常响应可能导致 SSE 不能正确结束
    """
    if len(chat_request.message) > settings.visitor_message_max_chars:
        # visitor 侧单条消息长度限制
        raise HTTPException(
            status_code=413,
            detail="Visitor message is too large.",
        )


async def visitor_stream_lease(
    project_uid: Annotated[str, Path(..., description="Project UID")],
    client_ip: ClientIPDeps,
    rate_limiter: VisitorRateLimiterDeps,
) -> AsyncIterator[VisitorStreamLease]:
    """Visitor 侧的流式对话租约依赖"""
    try:
        # 获取 visitor stream 租约
        lease = await rate_limiter.acquire_stream(
            ip=client_ip,
            project_uid=project_uid,
        )
    except VisitorRateLimitError as exc:
        raise exc

    try:
        yield lease
    finally:
        # 释放 visitor stream 租约
        await rate_limiter.release_stream(lease)


@router.post(
    "/project/{project_uid}/widget/{widget_uid}/chat/stream",
    response_class=EventSourceResponse,
)
async def stream_chat(
    chat_request: Annotated[VisitorChatRequest, Depends(get_visitor_chat_request)],
    _rate_limit: Annotated[None, Depends(enforce_visitor_chat_rate_limit)],
    _lease: Annotated[VisitorStreamLease, Depends(visitor_stream_lease)],
    project: ValidVisitorChatProjectDeps,
    _widget: Annotated[ProjectWidget, Depends(valid_visitor_widget)],
    completer: Annotated[FullCompleter, Depends(get_visitor_completer)],
    provider_with_model: Annotated[
        ProviderWithModelInternalRead, Depends(get_visitor_provider_with_model)
    ],
    chat_service: ChatOrchestratorServiceDeps,
    model_settings: Annotated[ModelSettings, Depends(get_visitor_model_settings)],
    rag_plugin: Annotated[RAGChatPlugin | None, Depends(get_rag_plugin)],
) -> AsyncIterable[ServerSentEvent]:
    """
    Visitor 侧的流式对话接口
    """
    async for event in chat_service.stream_rag_chat(
        project=project,
        chat_input=ChatInput(
            message=chat_request.message,
            chat_session_uid=chat_request.chat_session_uid,
        ),
        completer=completer,
        provider_with_model=provider_with_model,
        requester_type=ChatSessionType.VISITOR,
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


@router.post(
    "/project/{project_uid}/widget/{widget_uid}/generation/{generation_uid}/cancel",
    response_model=VisitorChatCancelResponse,
)
async def cancel_visitor_generation(
    _rate_limit: Annotated[None, Depends(enforce_visitor_project_rate_limit)],
    generation_registry: GenerationRegistryDeps,
    widget_uid: Annotated[str, Path(..., description="Widget UID")],
    generation_uid: Annotated[str, Path(..., description="生成任务 UID")],
):
    """取消 visitor 侧活跃 LLM 生成；已结束时幂等 no-op"""
    cancelled = generation_registry.cancel(generation_uid)
    return VisitorChatCancelResponse(
        widget_uid=widget_uid,
        generation_uid=generation_uid,
        cancelled=cancelled,
    )
