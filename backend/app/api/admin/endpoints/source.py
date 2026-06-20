from typing import Annotated, AsyncIterable
from pathlib import Path
import asyncio

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
    VectorDBDeps,
    FileStorageDeps,
    SourceItemUploadServiceDeps,
    WebCrawlSyncServiceDeps,
    SourceItemIndexingServiceDeps,
)
from ...schemas import IngestPausedResponse
from app.db.models import Source, SourceItem
from app.db.schemas import (
    SourceCreate,
    SourceRead,
    SourceInternal,
    SourceItemRead,
    WebCrawlConfig,
)
from app.utils import hostname_from_url, path_prefix_from_url
from app.core.constants import ALLOWED_FILE_TYPES, SourceType, CrawlEntryType
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
async def validate_and_normalize_config(
    source: ValidSourceDeps,
) -> WebCrawlConfig:
    """验证爬虫配置，并进行必要的规范化处理"""
    # 验证 source 类型是否支持 Web Crawl
    if source.source_type != SourceType.WEB_CRAWL:
        logger.warning(
            f"数据源 '{source.source_name}' 的类型 '{source.source_type}' 不支持 Web Crawl 同步"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source type does not support web crawl sync",
        )

    # 验证并规范化配置
    config = WebCrawlConfig.model_validate(source.web_crawl_config)

    if config.entry_type == CrawlEntryType.URL_LIST and not config.urls:
        raise ValueError("urls is required when entry_type is url_list")
    if config.entry_type == CrawlEntryType.SITEMAP_URL and not config.sitemap_url:
        raise ValueError("sitemap_url is required when entry_type is sitemap_url")
    if config.entry_type not in {
        CrawlEntryType.URL_LIST,
        CrawlEntryType.SITEMAP_URL,
    }:
        raise ValueError(f"Unsupported entry_type: {config.entry_type}")

    # 确保 config 配置字段的全面
    seed_urls: list[str] = []

    if config.urls:
        seed_urls.extend(str(url) for url in config.urls)
    if config.sitemap_url:
        seed_urls.append(str(config.sitemap_url))
    if config.site_root_url:
        seed_urls.append(str(config.site_root_url))

    # 推断 allowed_domains 配置
    allowed_domains = config.allowed_domains or sorted(
        {hostname_from_url(url) for url in seed_urls}
    )

    # 推断 include_paths 配置
    include_paths = config.include_paths
    if config.entry_type == CrawlEntryType.SITE_ROOT and not include_paths:
        include_paths = sorted(
            {path_prefix_from_url(url) for url in seed_urls}
        )  # 默认使用 site_root_url 的路径前缀作为 include_paths

    return config.model_copy(
        update={
            "allowed_domains": allowed_domains,
            "include_paths": include_paths,
        }
    )


# TODO: /new 需要重构，基于 source_type 实现不同的创建逻辑
@router.post("/new", response_model=SourceRead)
async def create_source(
    source_data: SourceCreate,
    source_crud: SourceCRUDeps,
    vector_db: VectorDBDeps,
):
    """
    创建新的数据源
    """

    logger.info(
        f"创建新的数据源，名称：{source_data.source_name}，类型：{source_data.source_type}"
    )

    # 检查同名数据源是否已存在
    existing_source = await source_crud.get_source_by_name(
        source_name=source_data.source_name
    )
    if existing_source:
        logger.warning(
            f"数据源名称 '{source_data.source_name}' 已存在，无法创建重复名称的数据源"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="source with the same name already exists",
        )

    # 创建向量集合
    try:
        # 生成系统内部使用的数据源模型
        source_internal = SourceInternal(**source_data.model_dump())
        await asyncio.to_thread(
            vector_db.create_collection, collection_name=source_internal.collection_name
        )
    except Exception as e:
        logger.error(f"创建向量集合失败：{e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create vector collection",
        )

    # 创建数据库记录
    try:
        new_source = await source_crud.create_source(source_data=source_internal)
        logger.info(
            f"数据源 '{source_data.source_name}' 创建成功，UID：{new_source.uid}"
        )
        return SourceRead.model_validate(new_source)
    except Exception as e:
        # 回滚向量集合
        logger.error(f"创建数据源记录失败：{e}，正在回滚向量集合...")
        try:
            await asyncio.to_thread(
                vector_db.delete_collection,
                collection_name=source_internal.collection_name,
            )
            logger.info(f"已回滚向量集合 '{source_internal.collection_name}'")
        except Exception as rollback_error:
            logger.error(f"回滚向量集合失败：{rollback_error}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create source and rollback vector collection",
            ) from rollback_error


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


@router.post("/{source_uid}/items/upload", response_model=SourceItemRead)
async def upload_source_item(
    source: ValidSourceDeps,
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


async def get_web_crawl_config(
    source: ValidSourceDeps,
) -> WebCrawlConfig:
    """依赖注入接口：获取已验证的 WebCrawlConfig 实例"""
    # 验证 source 类型是否支持 Web Crawl
    if source.source_type != SourceType.WEB_CRAWL:
        logger.warning(
            f"数据源 '{source.source_name}' 的类型 '{source.source_type}' 不支持 Web Crawl 同步"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source type does not support web crawl sync",
        )

    # 获取对应配置
    config = WebCrawlConfig.model_validate(source.web_crawl_config)
    if not config:
        logger.warning(
            f"数据源 '{source.source_name}' 的 Web Crawl 配置为空，无法进行同步"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Web crawl config is empty for this source",
        )

    return config


@router.post("/{source_uid}/crawl/sync", response_class=EventSourceResponse)
async def sync_web_crawl(
    source: ValidSourceDeps,
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
@router.post("/{source_uid}/items/indexing", response_class=EventSourceResponse)
async def indexing_source_items(
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


@router.post("/{source_uid}/items/pause", response_model=list[IngestPausedResponse])
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
