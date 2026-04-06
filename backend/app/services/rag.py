import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.rag.chromadb import chromadb, ChromaQueryItem
from app.rag.file_parser import FileParser
from app.core.models import VectorCollections, Documents
from app.core.schemas import (
    VectorCollectionInternal,
    VectorCollectionRead,
    DocumentRead,
)
from app.utils.calcu_file_hash import calculate_file_hash


class RAGService:
    async def create_collection(
        self, session: AsyncSession, collection_data: VectorCollectionInternal
    ) -> VectorCollectionRead:
        """创建新的 ChromaDB 集合"""
        logger.info(f"创建 ChromaDB 集合 '{collection_data.display_name}'")

        # 检查数据库中是否已存在同名集合记录
        result = await session.execute(
            select(1)
            .where(VectorCollections.display_name == collection_data.display_name)
            .limit(1)
        )
        if result.scalar():
            logger.warning(f"集合 '{collection_data.display_name}' 已存在")
            raise ValueError(
                f"Collection with name '{collection_data.display_name}' already exists"
            )

        try:
            # 创建向量集合
            await asyncio.to_thread(
                chromadb.create_collection,
                collection_name=collection_data.collection_name,  # 使用内部生成的 collection_name 字段
            )
        except ValueError as e:
            # 集合可能已存在或集合名不合法
            logger.warning(
                f"集合 '{collection_data.display_name}' 创建失败，错误信息：{e}"
            )
            raise

        try:
            # 数据库中创建集合记录
            new_collection = VectorCollections(**collection_data.model_dump())
            session.add(new_collection)
            await session.flush()

            logger.info(f"集合 '{collection_data.display_name}' 已创建")
            return VectorCollectionRead.model_validate(new_collection)
        except Exception as e:
            # 若数据库写入失败，回滚 Chroma 集合
            logger.error(
                f"集合 '{collection_data.display_name}' 数据库写入失败，准备回滚 Chroma 集合，错误信息：{e}"
            )
            try:
                await asyncio.to_thread(
                    chromadb.delete_collection,
                    collection_name=collection_data.collection_name,
                )
            except Exception as rollback_err:
                logger.error(
                    f"回滚 Chroma 集合失败，collection_name={collection_data.collection_name}, 错误信息：{rollback_err}"
                )
            raise

    async def get_collections(
        self, session: AsyncSession, *, limit: int = 10, offset: int = 0
    ) -> list[VectorCollectionRead]:
        """获取所有集合列表"""
        result = await session.execute(
            select(VectorCollections)
            .offset(offset)
            .limit(limit)
            .order_by(VectorCollections.created_at.desc())
        )
        collections = result.scalars().all()
        return [VectorCollectionRead.model_validate(col) for col in collections]

    async def process_and_store_document(
        self,
        session: AsyncSession,
        *,
        parser: FileParser,  # 解析器实例，便于后续扩展支持不同类型文档解析
        collection_uid: str,
        file_content: bytes,
        filename: str,
        source: str,
    ) -> DocumentRead:
        """
        解析文档内容并存储到指定集合中

        Args:
            session: 数据库会话
            parser: 文件解析器实例，负责将文件内容解析成文本块列表
            collection_uid: 目标集合 ID
            file_content: 文档文件内容
            filename: 文档文件名，网络爬取时传入 url 的最后一部分
            source: 文档来源，local_file 或 web_scrape

        Returns:
            DocumentRead 模型，包含文档基本信息
        """
        logger.info(f"处理并存入文档 '{filename}'，来源：{source}")

        # 获取 collection
        collection_res = await session.execute(
            select(VectorCollections).where(VectorCollections.uid == collection_uid)
        )
        collection = collection_res.scalar_one_or_none()
        if not collection:
            logger.error(f"未找到 collection_uid={collection_uid} 对应的集合")
            raise ValueError(f"Collection with uid {collection_uid} does not exist")

        # 检查文件是否已处理过（通过 file_hash 判断）
        # TODO: 可以考虑按照文件大小，控制是否需要扔到线程池中运行
        file_hash = calculate_file_hash(file_content)

        is_duplicate = await session.execute(
            select(1)
            .where(
                Documents.file_hash == file_hash,
                Documents.vector_collection_id == collection.id,
            )
            .limit(1)
        )
        if is_duplicate.scalar():
            logger.info(
                f"文档 '{filename}' 已存在于集合 UID {collection_uid} 中，跳过处理"
            )
            raise ValueError(
                f"Document with the same content already exists in the collection. Filename: '{filename}'"
            )

        # 解析文档内容为文本块列表
        # TODO: NOTE: 小心这里可能会有并发性能问题
        documents = await asyncio.to_thread(
            parser.parse, file_input=file_content, filename=filename
        )

        # 存储文本块到向量库
        stored_count = await asyncio.to_thread(
            chromadb.upsert_documents,
            collection_name=collection.collection_name,
            documents=documents,
            hash_key=file_hash,
        )

        # 写入文档数据
        new_document = Documents(
            filename=filename,
            source=source,
            file_hash=file_hash,
            vector_collection_id=collection.id,
        )
        session.add(new_document)
        await session.flush()

        logger.info(f"文档 '{filename}' 已处理并存储，文本块数量：{stored_count}")
        return DocumentRead.model_validate(new_document)

    async def get_related_documents(
        self,
        session: AsyncSession,
        *,
        collection_uid: str,
        query_text: str,
        top_k: int = 5,
    ) -> list[ChromaQueryItem]:
        """
        获取 collection_uid 对应向量集合，
        并执行向量库查询，返回与 query_text 相关文档内容
        """
        logger.info(
            f"进行向量库查询，collection_uid={collection_uid}, query_text='{query_text[:50]}', top_k={top_k}"
        )
        result = await session.execute(
            select(VectorCollections.collection_name).where(
                VectorCollections.uid == collection_uid,
            )
        )
        collection_name = result.scalar_one_or_none()

        if not collection_name:
            raise ValueError(
                f"Can not find vector collection for collection_uid={collection_uid}"
            )

        # 执行向量库查询，获取相关文档
        return await asyncio.to_thread(
            chromadb.query,
            collection_name=collection_name,
            query_text=query_text,
            top_k=top_k,
        )


def get_rag_service() -> RAGService:
    """依赖注入接口：提供 RAGService 实例"""
    return RAGService()
