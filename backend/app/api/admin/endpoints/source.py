from typing import Annotated
import uuid
import asyncio

from fastapi import APIRouter, UploadFile, Query, Depends, HTTPException, status
from loguru import logger

from ...deps import RAGServiceDeps, SourceCRUDeps, VectorDBDeps
from app.db.schemas import SourceCreate, SourceRead, SourceInternal, SourceItemRead
from app.parser import FileParser, file_parser_factory

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
