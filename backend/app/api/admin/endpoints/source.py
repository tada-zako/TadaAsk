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

from ...deps import RAGServiceDeps, SourceCRUDeps, VectorDBDeps, FileStorageDeps
from app.services import SourceItemService
from app.db.models import Source, SourceItem
from app.db.schemas import (
    SourceCreate,
    SourceRead,
    SourceInternal,
    SourceItemRead,
)
from app.parser import FileParser, file_parser_factory
from app.core.config import settings


# 相关配置
MAX_FILE_SIZE = settings.max_file_size  # 最大文件大小
MAX_FILE_COUNT = settings.max_file_count  # 最大文件数量

DOC_EXTS = {".pdf", ".docx", ".doc"}
DATA_EXTS = {".json", ".xml", ".yaml", ".yml"}
TEXT_EXTS = {".txt", ".md", ".html"}
CODE_EXTS = {".py", ".js", ".ts", ".java", ".cpp", ".c", ".go", ".rs", ".sql", ".sh"}

ALLOWED_FILE_TYPES = DOC_EXTS | DATA_EXTS | TEXT_EXTS | CODE_EXTS  # 允许的文件类型集合

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


def get_file_parser(file: UploadFile) -> FileParser:
    """文件解析器工厂：根据请求传输的文件类型返回对应的解析器实例"""
    file_type = "unknown"

    content_type = (file.content_type or "").lower()
    filename = (file.filename or "").lower()

    if content_type in {"application/pdf", "application/x-pdf"} or filename.endswith(
        ".pdf"
    ):
        file_type = "pdf"
    return file_parser_factory(file_type=file_type)


def get_source_item_service(
    source_crud: SourceCRUDeps,
    file_storage: FileStorageDeps,
) -> SourceItemService:
    """SourceItemService 依赖注入接口"""
    return SourceItemService(
        source_crud=source_crud,
        file_storage=file_storage,
    )


ValidSourceDeps = Annotated[Source, Depends(valid_source)]


# ===============================
# API 端点实现
# ===============================
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
    source_item_service: Annotated[SourceItemService, Depends(get_source_item_service)],
):
    """
    文件上传接口；支持单文件和多文件

    Args:
        source: 验证存在的 source 实例
        validated_files: 已验证文件列表
        source_item_service: SourceItemService 依赖注入

    Returns:
        上传成功的 SourceItemRead 列表
    """

    return await source_item_service.upload_file(
        validated_files=validated_files,
        source=source,
    )


async def valid_source_items(
    source_crud: SourceCRUDeps,
    source: ValidSourceDeps,
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
    """根据数据项 UID 列表获取数据项详情列表"""
    if len(source_item_uids) > MAX_INGEST_SOURCE_ITEMS:
        logger.warning(
            f"请求 ingest 的数据项数量 {len(source_item_uids)} 超过限制 {MAX_INGEST_SOURCE_ITEMS}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Number of source items to ingest exceeds the maximum allowed count of {MAX_INGEST_SOURCE_ITEMS}",
        )

    result = await source_crud.get_source_items_by_uids_with_document_for_source(
        source_id=source.id, item_uids=source_item_uids
    )
    # TODO: 提前验证 source_item.status，确保已经完成的 item，不进入 ingest
    return list(result)


# TODO: 缺少文件存在验证，如果用户上传了相同的文件，应该复用已经存在的文件
@router.post("/{source_uid}/document/ingest", response_model=EventSourceResponse)
async def upsert_document(
    source: ValidSourceDeps,
    source_items: Annotated[
        list[SourceItem],
        Depends(valid_source_items),
    ],
    source_crud: SourceCRUDeps,
    rag_service: RAGServiceDeps,
) -> AsyncIterable[ServerSentEvent]:
    """
    解析文档
    """
