from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, UploadFile, Query
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.db import get_db
from app.services.rag import get_rag_service, RAGService
from app.tools.file_parser import FileParser, PDFParser
from app.db.schemas import SourceCreate, SourceRead, SourceInternal, SourceItemRead

router = APIRouter(prefix="/knowledge-base", tags=["Knowledge-Base"])


def parser_factory(file: UploadFile) -> FileParser:
    """文件解析器工厂：根据请求传输的文件类型返回对应的解析器实例"""
    content_type = (file.content_type or "").lower()
    filename = (file.filename or "").lower()
    if content_type in {"application/pdf", "application/x-pdf"} or filename.endswith(
        ".pdf"
    ):
        return PDFParser()
    else:
        raise ValueError(f"Unsupported file type for parsing: {file.content_type}")


@router.post("/collection/new", response_model=SourceRead)
async def create_collection(
    payload: SourceCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
    rag_service: Annotated[RAGService, Depends(get_rag_service)],
):
    """
    创建新的向量集合（知识库）

    Args:
        payload: 包含 collection 的 display_name 和 collection_name 的请求体
        session: 数据库会话，通过依赖注入获取
        rag_service: RAGService 实例，通过依赖注入获取

    Returns:
    """
    logger.info(f"创建新的向量集合，display_name={payload.source_name}")

    # 将请求体转换为内部使用的模型
    internal_payload = SourceInternal.model_validate(payload.model_dump())

    # 调用 RAG 业务代码
    collection = await rag_service.create_collection(session, internal_payload)
    return collection


@router.get("/collections", response_model=list[SourceRead])
async def list_collections(
    session: Annotated[AsyncSession, Depends(get_db)],
    rag_service: Annotated[RAGService, Depends(get_rag_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """
    获取所有向量集合（知识库）列表

    Args:
        session: 数据库会话，通过依赖注入获取
        rag_service: RAGService 实例，通过依赖注入获取
        limit: 每页集合数量，默认为 10，范围 1-100
        offset: 偏移量，用于分页，默认为 0

    Returns:
        向量集合列表
    """
    logger.info("获取向量集合列表")

    # 调用 RAG 业务代码获取集合列表
    collections = await rag_service.get_collections(session, limit=limit, offset=offset)
    return collections


@router.post("/{collection_uid}/documents/upsert", response_model=SourceItemRead)
async def upsert_document(
    collection_uid: str,
    file: UploadFile,
    session: Annotated[AsyncSession, Depends(get_db)],
    file_parser: Annotated[FileParser, Depends(parser_factory)],
    rag_service: Annotated[RAGService, Depends(get_rag_service)],
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
        session,
        parser=file_parser,
        collection_uid=collection_uid,
        file_content=await file.read(),
        filename=filename,
        source="local_file",
    )
    return document
