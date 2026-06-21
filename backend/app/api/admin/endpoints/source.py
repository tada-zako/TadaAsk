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
)
from fastapi.sse import EventSourceResponse, ServerSentEvent
from loguru import logger

from ...deps import (
    SourceCRUDeps,
    SourceCreationServiceDeps,
    SourceItemUploadServiceDeps,
    WebCrawlSyncServiceDeps,
    SourceItemIndexingServiceDeps,
)
from ...schemas import IngestPausedResponse
from app.db.models import Source, SourceItem
from app.db.schemas import (
    SourceCreate,
    SourceRead,
    SourceItemRead,
    WebCrawlConfig,
)
from app.core.constants import ALLOWED_FILE_TYPES, SourceType
from app.core.exceptions import (
    SourceCreateStorageError,
    SourceCreateValidationError,
    SourceCreateConflictError,
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


@router.post("/{source_uid}/crawl/sync", response_class=EventSourceResponse)
async def sync_web_crawl(
    source: Annotated[Source, Depends(valid_web_crawl_source)],
    config: Annotated[WebCrawlConfig, Depends(get_web_crawl_config)],
    web_crawl_sync_service: WebCrawlSyncServiceDeps,
) -> AsyncIterable[ServerSentEvent]:
    """
    触发 Web Crawl 同步操作，返回 SSE 流式事件
    """
    async for event in web_crawl_sync_service.sync_source(
        source=source,
        config=config,
    ):
        yield ServerSentEvent(
            event=event.event,
            data=event.model_dump_json(
                exclude={"event"},
                by_alias=True,
            ),
        )


# TODO: 缺少文件存在验证，如果用户上传了相同的文件，应该复用已经存在的文件
@router.post("/{source_uid}/document/indexing", response_class=EventSourceResponse)
async def indexing_documents(
    source_uid: Annotated[str, Depends(valid_source_uid)],
    source_item_uids: Annotated[
        list[str],
        Depends(valid_source_item_uids),
    ],
    source_item_indexing_service: SourceItemIndexingServiceDeps,
) -> AsyncIterable[ServerSentEvent]:
    """
    解析文档
    """
    async for event in source_item_indexing_service.ingest_source_items(
        source_uid=source_uid,
        source_item_uids=source_item_uids,
    ):
        yield ServerSentEvent(
            event=event.event,
            data=event.model_dump_json(
                exclude={"event"},
                by_alias=True,
            ),
        )


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


@router.post("/{source_uid}/document/resume", response_class=EventSourceResponse)
async def resume_ingest(
    source_crud: SourceCRUDeps,
    source_uid: Annotated[str, Depends(valid_source_uid)],
    source_items: Annotated[
        list[SourceItem],
        Depends(valid_source_items),
    ],
    source_item_indexing_service: SourceItemIndexingServiceDeps,
) -> AsyncIterable[ServerSentEvent]:
    """
    恢复文档解析
    """
    async for event in source_item_indexing_service.resume_ingest(
        source_uid=source_uid,
        source_items=source_items,
    ):
        yield ServerSentEvent(
            event=event.event,
            data=event.model_dump_json(
                exclude={"event"},
                by_alias=True,
            ),
        )


# NOTE: 文档检索时，需要注意 status = "completed" 的数据项，才是可以被检索的；
