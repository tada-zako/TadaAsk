from typing import Annotated
from pathlib import Path
import uuid
import asyncio

from fastapi import (
    APIRouter,
    UploadFile,
    Query,
    Depends,
    Path as FastAPIPath,
    HTTPException,
    status,
    BackgroundTasks,
)
from loguru import logger

from ...deps import RAGServiceDeps, SourceCRUDeps, VectorDBDeps
from app.db.models import Source
from app.db.schemas import (
    SourceCreate,
    SourceRead,
    SourceInternal,
    SourceItemRead,
    SourceItemInternal,
)
from app.parser import FileParser, file_parser_factory
from app.utils import calculate_file_hash
from app.core.config import settings


# 相关配置
MAX_FILE_SIZE = settings.max_file_size  # 最大文件大小
MAX_FILE_COUNT = settings.max_file_count  # 最大文件数量

DOC_EXTS = {".pdf", ".docx", ".doc"}
DATA_EXTS = {".json", ".xml", ".yaml", ".yml"}
TEXT_EXTS = {".txt", ".md", ".html"}
CODE_EXTS = {".py", ".js", ".ts", ".java", ".cpp", ".c", ".go", ".rs", ".sql", ".sh"}

ALLOWED_FILE_TYPES = DOC_EXTS | DATA_EXTS | TEXT_EXTS | CODE_EXTS  # 允许的文件类型集合

UPLOAD_FOLDER = Path(settings.upload_folder_path)  # 文件上传存储路径
# 确保路径存在
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)


router = APIRouter()


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


FileParserDeps = Annotated[FileParser, Depends(get_file_parser)]


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


def save_file_to_upload_folder(file_content: bytes, save_path: Path, filename: str):
    """将文件内容保存到上传目录，文件名使用哈希值加原始扩展名"""
    try:
        save_path.parent.mkdir(parents=True, exist_ok=True)  # 确保目录存在

        # 同步写入；避免异步阻塞主线程
        with open(save_path, "wb") as f:
            f.write(file_content)

        logger.info(f"文件 '{filename}' 已保存到 '{save_path}'")
    except Exception as e:
        logger.error(f"保存文件 '{filename}' 失败：{e}")


async def valid_source(
    source_crud: SourceCRUDeps,
    source_uid: Annotated[str, FastAPIPath(..., description="Project UID")],
) -> Source:
    """验证 source UID 是否有效，返回 source 实例或抛出 HTTPException"""
    source = await source_crud.get_source_by_uid(source_uid=source_uid)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


@router.post("/{source_uid}/items/upload", response_model=SourceItemRead)
async def upload_source_item(
    source: Annotated[Source, Depends(valid_source)],
    source_crud: SourceCRUDeps,
    validated_files: Annotated[list[UploadFile], Depends(valid_files)],
    background_tasks: BackgroundTasks,
):
    """
    文件上传接口；支持单文件和多文件

    Args:
        source: 验证存在的 source 实例
        source_crud: SourceCRUD 实例
        validated_files: 已验证文件列表
        background_tasks: 用于添加后台任务

    Returns:
        上传成功的 SourceItemRead 列表
    """
    source_items = []

    for file in validated_files:
        # 1. 计算文件哈希值
        file_content = await file.read()
        file_hash = calculate_file_hash(
            file_content
        )  # NOTE: 假设 calculate_file_hash 处理速度较快

        filename: str = file.filename  # type: ignore
        ext = Path(filename).suffix.lower()
        # 使用 hash 前两位作为子目录
        save_path = UPLOAD_FOLDER / file_hash[:2] / f"{file_hash}{ext}"

        # 2. 添加文件存储到上传目录任务
        background_tasks.add_task(
            save_file_to_upload_folder,
            file_content=file_content,
            save_path=save_path,
            filename=filename,
        )

        # 3. 创建 SourceItemInternal 实例
        source_items.append(
            SourceItemInternal(
                title=filename,
                local_path=str(save_path),
                origin_url=None,
                item_hash=file_hash,
            )
        )

    # 4. 执行写库操作
    created_items = await source_crud.add_source_items(
        source=source, items_data=source_items
    )

    return [SourceItemRead.model_validate(item) for item in created_items]


@router.post("/{source_uid}/documents/add", response_model=SourceItemRead)
async def upsert_document(
    collection_uid: str,
    file: UploadFile,
    file_parser: FileParserDeps,
    rag_service: RAGServiceDeps,
):
    """
    上传文件并将其内容解析后存储为文档

    Args:
        collection_uid: 目标集合 UID，从路径参数获取
        file: 上传的文件，通过请求体获取
        session: 数据库会话，通过依赖注入获取
        file_parser: 文件解析器实例，通过工厂函数和依赖注入获取
        rag_service: RAGService 实例，通过依赖注入获取

    Returns:
    """
    logger.info(f"上传文件 '{file.filename}' 到集合 UID '{collection_uid}'")

    # 调用 RAG 业务代码处理文件上传和文档存储
    filename = file.filename or f"unnamed_{uuid.uuid4()}"

    document = await rag_service.process_and_store_document(
        parser=file_parser,
        collection_uid=collection_uid,
        file_content=await file.read(),
        filename=filename,
        source="local_file",
    )
    return document
