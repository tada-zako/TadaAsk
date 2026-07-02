from typing import Annotated, AsyncIterable
from pathlib import Path

from fastapi import (
    APIRouter,
    UploadFile,
    Depends,
    Query,
    Path as FastAPIPath,
    Body,
    HTTPException,
    status,
    Header,
)
from fastapi.sse import EventSourceResponse, ServerSentEvent
from loguru import logger

from ...deps import (
    SourceCRUDeps,
    SourceCreationServiceDeps,
    SourceItemServiceDeps,
    SourceItemUploadServiceDeps,
    WebCrawlSyncServiceDeps,
    SourceItemIndexingServiceDeps,
    RAGJobManagerDeps,
)
from ...schemas import (
    IngestPausedResponse,
    SourceItemDeleteResponse,
    RAGJobStartResponse,
    RAGJobRead,
    ActiveRAGJobsResponse,
)
from app.db.models import Source, SourceItem
from app.db.schemas import (
    SourceCreate,
    SourceRead,
    SourceItemRead,
    WebCrawlConfig,
)
from app.core.constants import (
    ALLOWED_FILE_TYPES,
    SourceItemProcessStatus,
    SourceType,
    RAGJobType,
)
from app.core.exceptions import (
    SourceCreateStorageError,
    SourceCreateValidationError,
    SourceCreateConflictError,
    SourceItemDeleteConflictError,
)
from app.core.config import settings


# 相关配置
MAX_FILE_SIZE = settings.max_file_size  # 最大文件大小
MAX_FILE_COUNT = settings.max_file_count  # 最大文件数量
MAX_INGEST_SOURCE_ITEMS = 10  # 每次 ingest 的最大数据项数量


router = APIRouter()


# ===============================
# 依赖函数
# ===============================
def valid_files(files: list[UploadFile]) -> list[UploadFile]:
    """
    验证上传的文件列表，过滤掉不合法的文件并返回合法文件列表
    验证策略：
        1. 过滤掉文件名为空的文件
        2. 验证文件类型是否合法（根据扩展名）
        3. 验证文件大小是否超过限制
        4. 验证文件数量是否超过限制
    返回合法的文件列表
    """
    validated_files: list[UploadFile] = []

    for file in files:
        # 1. 过滤空文件名
        if not file.filename:
            continue

        # 2. 检验后缀名合法性
        ext = Path(file.filename).suffix.lower()
        if ext not in ALLOWED_FILE_TYPES:
            logger.warning(f"文件 '{file.filename}' 的类型 '{ext}' 不受支持")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type '{ext}' is not supported",
            )

        # 3. 校验文件大小
        file_size = file.size or 0
        if file_size > MAX_FILE_SIZE:
            logger.warning(
                f"文件 '{file.filename}' 的大小 {file_size} 超过限制 {MAX_FILE_SIZE}"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File '{file.filename}' exceeds the maximum allowed size of {MAX_FILE_SIZE} bytes",
            )

        validated_files.append(file)

    # 4. 校验文件数量
    if len(validated_files) > MAX_FILE_COUNT:
        logger.warning(f"上传文件数量 {len(validated_files)} 超过限制 {MAX_FILE_COUNT}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Number of uploaded files exceeds the maximum allowed count of {MAX_FILE_COUNT}",
        )

    # 5. 如果没有合法文件，抛出异常
    if not validated_files:
        logger.warning("未上传有效文件")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No valid files uploaded"
        )

    return validated_files


async def valid_source(
    source_crud: SourceCRUDeps,
    source_uid: Annotated[str, FastAPIPath(..., description="Project UID")],
) -> Source:
    """验证 source UID 是否有效，返回 source 实例或抛出 HTTPException"""
    source = await source_crud.get_source_by_uid(source_uid=source_uid)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


async def valid_source_uid(
    source_crud: SourceCRUDeps,
    source_uid: Annotated[str, FastAPIPath(..., description="Project UID")],
) -> str:
    """验证 source UID 是否有效，返回 source_uid 或抛出 HTTPException"""
    source = await source_crud.get_source_by_uid(source_uid=source_uid)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return source_uid


async def valid_source_item(
    source_crud: SourceCRUDeps,
    source: "ValidSourceDeps",
    source_item_uid: Annotated[
        str,
        Body(
            ...,
            alias="itemUid",
            embed=True,
            description="数据项 UID",
        ),
    ],
) -> SourceItem:
    """验证数据项 UID 是否有效，返回数据项实例或抛出 HTTPException"""
    result = await source_crud.get_source_item_by_uid_for_source(
        source_id=source.id, item_uid=source_item_uid
    )

    if not result:
        logger.warning(
            f"数据项 UID '{source_item_uid}' 在数据源 '{source.source_name}' 中未找到"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source item not found",
        )

    # TODO: 提前验证 source_item.status，确保已经完成的 item，不进入 ingest
    return result


async def valid_source_item_from_path(
    source_crud: SourceCRUDeps,
    source: "ValidSourceDeps",
    source_item_uid: Annotated[
        str,
        FastAPIPath(..., description="数据项 UID"),
    ],
) -> SourceItem:
    """验证 path 中的数据项 UID 是否属于当前 source"""
    result = await source_crud.get_source_item_by_uid_for_source(
        source_id=source.id, item_uid=source_item_uid
    )

    if not result:
        logger.warning(
            f"数据项 UID '{source_item_uid}' 在数据源 '{source.source_name}' 中未找到"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source item not found",
        )

    return result


async def valid_source_items(
    source_crud: SourceCRUDeps,
    source: "ValidSourceDeps",
    source_item_uids: Annotated[
        list[str],
        Body(
            ...,
            alias="itemUids",
            embed=True,
            description="数据项 UID 列表",
        ),
    ],
) -> list[SourceItem]:
    """验证数据项 UID 列表，返回数据项实例列表或抛出 HTTPException"""
    if len(source_item_uids) > MAX_INGEST_SOURCE_ITEMS:
        logger.warning(
            f"请求 ingest 的数据项数量 {len(source_item_uids)} 超过限制 {MAX_INGEST_SOURCE_ITEMS}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Number of source items to ingest exceeds the maximum allowed count of {MAX_INGEST_SOURCE_ITEMS}",
        )

    source_item_uids = list(dict.fromkeys(source_item_uids))
    result = await source_crud.get_source_items_by_uids_for_source(
        source_id=source.id, item_uids=source_item_uids
    )

    valid_uids = [item.uid for item in result]
    missing_uids = [uid for uid in source_item_uids if uid not in valid_uids]
    if missing_uids:
        logger.warning(
            f"数据项 UID 列表中有无效 UID，source '{source.source_name}' 中未找到的 UID: {missing_uids}"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source items not found for UIDs: {missing_uids}",
        )

    return list(result)


async def valid_source_item_uids(
    source_crud: SourceCRUDeps,
    source: "ValidSourceDeps",
    source_item_uids: Annotated[
        list[str],
        Body(
            ...,
            alias="itemUids",
            embed=True,
            description="数据项 UID 列表",
        ),
    ],
) -> list[str]:
    """验证数据项 UID 列表，返回有效的 UID 列表或抛出 HTTPException"""
    if len(source_item_uids) > MAX_INGEST_SOURCE_ITEMS:
        logger.warning(
            f"请求 ingest 的数据项数量 {len(source_item_uids)} 超过限制 {MAX_INGEST_SOURCE_ITEMS}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Number of source items to ingest exceeds the maximum allowed count of {MAX_INGEST_SOURCE_ITEMS}",
        )

    source_item_uids = list(dict.fromkeys(source_item_uids))
    result = await source_crud.get_source_items_by_uids_for_source(
        source_id=source.id, item_uids=source_item_uids
    )

    valid_uids = [item.uid for item in result]
    missing_uids = [uid for uid in source_item_uids if uid not in valid_uids]
    if missing_uids:
        logger.warning(
            f"数据项 UID 列表中有无效 UID，source '{source.source_name}' 中未找到的 UID: {missing_uids}"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source items not found for UIDs: {missing_uids}",
        )

    return valid_uids


ValidSourceDeps = Annotated[Source, Depends(valid_source)]


def _parse_last_event_sequence(last_event_id: str | None) -> int:
    """解析 SSE Last-Event-ID；避免非法值"""
    if not last_event_id:
        return 0

    try:
        sequence = int(last_event_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Last-Event-ID",
        ) from exc

    if sequence < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Last-Event-ID",
        )

    return sequence


def _source_rag_active_group(source_uid: str) -> str:
    """同一个 source 的 RAG 后台任务互斥。"""
    return f"source_rag:{source_uid}"


# ===============================
# API 端点实现
# ===============================
@router.post("/new", response_model=SourceRead)
async def create_source(
    source_data: Annotated[SourceCreate, Body(..., description="数据源创建信息")],
    source_creation_service: SourceCreationServiceDeps,
):
    try:
        source = await source_creation_service.create_source(source_data=source_data)
    except SourceCreateConflictError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SourceCreateValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SourceCreateStorageError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return SourceRead.model_validate(source)


@router.get("/list", response_model=list[SourceRead])
async def list_sources(
    source_crud: SourceCRUDeps,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """
    获取所有数据源列表，支持分页

    Args:
        limit: 分页参数，返回结果的最大数量，默认为 10，范围 1-100
        offset: 分页参数，返回结果的偏移量，默认为 0，必须为非负整数
    """
    logger.info(f"获取数据源列表，limit={limit}, offset={offset}")

    sources = await source_crud.list_sources(limit=limit, offset=offset)
    return [SourceRead.model_validate(source) for source in sources]


async def valid_local_file_source(
    source: ValidSourceDeps,
) -> Source:
    """验证数据源是否为本地文件类型，返回 source 实例或抛出 HTTPException"""
    if source.source_type != SourceType.LOCAL_FILE:
        logger.warning(
            f"数据源 '{source.source_name}' 的类型 '{source.source_type}' 不支持文件上传"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source type does not support file upload",
        )
    return source


@router.post("/{source_uid}/items/upload", response_model=list[SourceItemRead])
async def upload_source_item(
    source: Annotated[Source, Depends(valid_local_file_source)],
    validated_files: Annotated[list[UploadFile], Depends(valid_files)],
    source_item_upload_service: SourceItemUploadServiceDeps,
):
    """
    文件上传接口；支持单文件和多文件

    Args:
        source: 验证存在的 source 实例
        validated_files: 已验证文件列表
        source_item_upload_service: 依赖注入的 SourceItemUploadService 实例

    Returns:
        上传成功的 SourceItemRead 列表
    """

    return await source_item_upload_service.upload_file(
        validated_files=validated_files,
        source=source,
    )


@router.get("/{source_uid}/items", response_model=list[SourceItemRead])
async def list_source_items(
    source: ValidSourceDeps,
    source_crud: SourceCRUDeps,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """获取 source 下的数据项列表"""
    items = await source_crud.list_source_items_by_source_id(
        source_id=source.id,
        limit=limit,
        offset=offset,
    )
    return [SourceItemRead.model_validate(item) for item in items]


@router.delete(
    "/{source_uid}/items/{source_item_uid}", response_model=SourceItemDeleteResponse
)
async def delete_source_item(
    source: ValidSourceDeps,
    source_item: Annotated[SourceItem, Depends(valid_source_item_from_path)],
    source_item_service: SourceItemServiceDeps,
):
    """删除 source item，并清理对应的向量与文件对象"""
    try:
        result = await source_item_service.delete_source_item(
            source=source,
            source_item=source_item,
        )
    except SourceItemDeleteConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return SourceItemDeleteResponse(
        source_uid=source.uid,
        source_item_uid=source_item.uid,
        deleted_vector_count=result.deleted_vector_count,
        file_deleted=result.file_deleted,
    )


async def valid_web_crawl_source(
    source: ValidSourceDeps,
) -> Source:
    """验证数据源是否为 Web Crawl 类型，返回 source 实例或抛出 HTTPException"""
    if source.source_type != SourceType.WEB_CRAWL:
        logger.warning(
            f"数据源 '{source.source_name}' 的类型 '{source.source_type}' 不支持 Web Crawl 同步"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source type does not support web crawl sync",
        )
    return source


async def get_web_crawl_config(
    source: Annotated[Source, Depends(valid_web_crawl_source)],
) -> WebCrawlConfig:
    """依赖注入接口：获取已验证的 WebCrawlConfig 实例"""
    # 获取对应配置
    if not source.web_crawl_config:
        logger.warning(
            f"数据源 '{source.source_name}' 的 Web Crawl 配置为空，无法进行同步"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Web crawl config is empty for this source",
        )

    return WebCrawlConfig.model_validate(source.web_crawl_config)


@router.post(
    "/{source_uid}/crawl/sync",
    response_model=RAGJobStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def sync_web_crawl(
    source: Annotated[Source, Depends(valid_web_crawl_source)],
    config: Annotated[WebCrawlConfig, Depends(get_web_crawl_config)],
    web_crawl_sync_service: WebCrawlSyncServiceDeps,
    rag_job_manager: RAGJobManagerDeps,
) -> RAGJobStartResponse:
    """
    创建 Web Crawl 同步任务
    """
    source_uid = source.uid

    async def run_web_crawl(_):
        """web crawl sync service 封装函数；兼容 job manager 调用"""
        async for event in web_crawl_sync_service.sync_source(
            source_uid=source_uid,
            config=config,
        ):
            yield event

    job = await rag_job_manager.start_job(
        job_type=RAGJobType.WEB_CRAWL_SYNC,
        source_uid=source_uid,
        active_group=_source_rag_active_group(source_uid),
        runner=run_web_crawl,
    )

    return RAGJobStartResponse.model_validate(job)


# TODO: 缺少文件存在验证，如果用户上传了相同的文件，应该复用已经存在的文件
@router.post(
    "/{source_uid}/document/indexing",
    response_model=RAGJobStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def indexing_documents(
    source_uid: Annotated[str, Depends(valid_source_uid)],
    source_item_uids: Annotated[
        list[str],
        Depends(valid_source_item_uids),
    ],
    source_item_indexing_service: SourceItemIndexingServiceDeps,
    rag_job_manager: RAGJobManagerDeps,
) -> RAGJobStartResponse:
    """
    创建 index 任务
    """

    async def run_indexing(_):
        """文档 indexing service 封装函数；兼容 job manager 调用"""
        async for event in source_item_indexing_service.ingest_source_items(
            source_uid=source_uid,
            source_item_uids=source_item_uids,
        ):
            yield event

    job = await rag_job_manager.start_job(
        job_type=RAGJobType.INDEXING,
        source_uid=source_uid,
        source_item_uids=source_item_uids,
        active_group=_source_rag_active_group(source_uid),
        runner=run_indexing,
    )

    return RAGJobStartResponse.model_validate(job)


@router.get(
    "/jobs/{job_uid}/events",
    response_class=EventSourceResponse,
)
async def stream_rag_job_events(
    job_uid: str,
    rag_job_manager: RAGJobManagerDeps,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> AsyncIterable[ServerSentEvent]:
    """RAG job SSE 观察接口"""
    job = rag_job_manager.get_job(job_uid)
    if not job:
        # 验证 job_uid
        raise HTTPException(status_code=404, detail="RAG job not found")

    # 从 Last-Event-ID 头部获取上次事件的 sequence
    after_sequence = _parse_last_event_sequence(last_event_id)

    # 订阅 job 事件流，并持续输出 SSE
    async for stored in rag_job_manager.subscribe(
        job_uid=job_uid,
        after_sequence=after_sequence,
    ):
        yield ServerSentEvent(
            id=str(stored.sequence),
            event=stored.event.event,
            data=stored.event.model_dump_json(exclude={"event"}, by_alias=True),
        )


@router.get(
    "/jobs/active",
    response_model=ActiveRAGJobsResponse,
)
async def list_active_rag_jobs(
    rag_job_manager: RAGJobManagerDeps,
) -> ActiveRAGJobsResponse:
    """获取所有正在运行的 RAG job。"""
    return ActiveRAGJobsResponse(
        jobs=[
            RAGJobRead.model_validate(job) for job in rag_job_manager.list_active_jobs()
        ]
    )


@router.get("/jobs/{job_uid}", response_model=RAGJobRead)
async def get_rag_job(
    job_uid: str,
    rag_job_manager: RAGJobManagerDeps,
) -> RAGJobRead:
    """获取指定 RAG job 状态。"""
    job = rag_job_manager.get_job(job_uid)
    if not job:
        raise HTTPException(status_code=404, detail="RAG job not found")

    return RAGJobRead.model_validate(job)


@router.post("/{source_uid}/document/pause", response_model=list[IngestPausedResponse])
async def pause_ingest(
    source_crud: SourceCRUDeps,
    source: ValidSourceDeps,
    source_items: Annotated[
        list[SourceItem],
        Depends(valid_source_items),
    ],
    source_item_indexing_service: SourceItemIndexingServiceDeps,
) -> list[IngestPausedResponse]:
    """
    暂停文档解析
    """
    return await source_item_indexing_service.request_pause_ingest(
        source_crud=source_crud,
        source=source,
        source_items=source_items,
    )


@router.post(
    "/{source_uid}/document/resume",
    response_model=RAGJobStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def resume_ingest(
    source_uid: Annotated[str, Depends(valid_source_uid)],
    source_items: Annotated[
        list[SourceItem],
        Depends(valid_source_items),
    ],
    source_item_indexing_service: SourceItemIndexingServiceDeps,
    rag_job_manager: RAGJobManagerDeps,
) -> RAGJobStartResponse:
    """
    创建恢复文档解析任务
    """

    not_paused_uids = [
        item.uid
        for item in source_items
        if item.status != SourceItemProcessStatus.PAUSED
    ]
    if not_paused_uids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Source items are not paused: {not_paused_uids}",
        )

    source_item_uids = [item.uid for item in source_items]

    async def run_resume(_):
        """文档 resume service 封装函数；兼容 job manager 调用"""
        async for event in source_item_indexing_service.resume_source_items(
            source_uid=source_uid,
            source_item_uids=source_item_uids,
        ):
            yield event

    job = await rag_job_manager.start_job(
        job_type=RAGJobType.RESUME_INGEST,
        source_uid=source_uid,
        source_item_uids=source_item_uids,
        active_group=_source_rag_active_group(source_uid),
        runner=run_resume,
    )

    return RAGJobStartResponse.model_validate(job)


# NOTE: 文档检索时，需要注意 status = "completed" 的数据项，才是可以被检索的；
