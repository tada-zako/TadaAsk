import asyncio
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import numpy as np
from numpy.typing import NDArray
from loguru import logger

from app.rag import (
    VectorQueryResult,
    VectorDatabase,
    TextChunk,
    TextSplitter,
    EmbeddingProvider,
    RerankProvider,
    FTSProvider,
    QueryExpander,
)
from app.parser import FileParser, ParsedDocument
from app.storage import FileStorage
from app.providers import Message
from app.db.models import Source, SourceItem, DocumentContent, DocumentChunk
from app.db.schemas import (
    SourceInternal,
    SourceRead,
    SourceItemRead,
)
from app.crud import SourceCRUD
from app.utils.calcu_file_hash import calculate_file_hash

# TODO: 需要完整重构，新增的 Project 模型尚未与 Service 集成

# vector_id 使用 UUIDv5 生成
RAG_NAMESPACE = uuid.UUID("2fbcbf86-2bb8-4c0c-92b7-c8a4840dbff4")  # 专属命名空间


def generate_vector_id(source_item_id: int, chunk_index: int) -> str:
    """基于 UUIDv5 生成向量 ID"""
    name = f"{source_item_id}_{chunk_index}"
    return str(uuid.uuid5(RAG_NAMESPACE, name))


# TODO: "chat messages 构建方法后续提升到 Service 层，确保 messages 构建与 Provider 无关"
# def build_chat_messages(
#     self,
#     document: list[VectorQueryItem],
#     user_message: str,
#     chat_history: list[ChatMessageInternal] | None = None,
# ) -> list[Message]:
#     """
#     构建符合 Gemini LLM 请求接口格式的消息实例
#     """
#     history_contents: list[types.ContentOrDict] | None = None
#     if chat_history:
#         history_contents = [
#             types.Content(
#                 role="model" if entry.role == "assistant" else "user",
#                 parts=[types.Part(text=entry.message)],
#             )
#             for entry in chat_history
#         ]

#     # NOTE: 目前只提供静态系统提示词
#     system_prompt = DEFAULT_SYSTEM_PROMPT

#     if document:
#         # 允许 document 为空
#         context = "\n<Context>\n"
#         for doc in document:
#             context += (
#                 f"[context{doc.id}]:\n{doc.document}\n"
#                 + f"Metadata: {doc.metadata}\n\n"
#             )
#         context += "</Context>\n"

#         user_message = (
#             context + "\n<user_message>\n" + user_message + "\n</user_message>\n"
#         )

#     return [
#         Message(role="system", content=system_prompt),
#     ]


class FileParserFactory:
    def generate(self, file_type: str) -> FileParser:
        # 假设有这么个接口
        ...


class RAGService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        file_storage: FileStorage,
        vector_db: VectorDatabase,
        text_splitter: TextSplitter,
        embedding: EmbeddingProvider,
        query_expander: QueryExpander,
        reranker: RerankProvider,
        fts_provider: FTSProvider,
        file_parser_factory: FileParserFactory,
    ):
        """具体的参数由依赖注入"""
        self.session = session
        self.file_storage = file_storage
        self.vector_db = vector_db
        self.text_splitter = text_splitter
        self.embedding = embedding
        self.query_expander = query_expander
        self.reranker = reranker
        self.fts_provider = fts_provider
        self.file_parser_factory = file_parser_factory

    async def upload_file(
        self,
        *,
        validated_files: list[UploadFile],
        source: Source,
        source_crud: SourceCRUD,
    ) -> list[SourceItemRead]:
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
            storage_key = f"{file_hash[:2]}/{file_hash}{ext}"

            # 2. 文件查重
            file_exists = await self.file_storage.exists(key=storage_key)

            # 3. 文件存储
            if not file_exists:
                await self.file_storage.save_file(key=storage_key, content=file_content)
                logger.info(
                    f"文件 '{filename}' 已保存到存储系统，存储键：{storage_key}"
                )
            else:
                logger.info(
                    f"文件 '{filename}' 已存在于存储系统，存储键：{storage_key}，跳过保存"
                )

            # 4. 创建 SourceItemInternal 实例
            source_items.append(
                SourceItemInternal(
                    title=filename,
                    storage_key=storage_key,
                    origin_url=None,
                    item_hash=file_hash,
                )
            )

        # 5. 执行写库操作
        created_items = await source_crud.add_source_items(
            source=source, items_data=source_items
        )

        return [SourceItemRead.model_validate(item) for item in created_items]

    async def process_and_store_document(
        self,
        *,
        parser: FileParser,  # 解析器实例，便于后续扩展支持不同类型文档解析
        collection_uid: str,
        file_content: bytes,
        filename: str,
        source: str,
    ) -> SourceItemRead:
        """
        解析文档内容并存储到指定集合中

        Args:
            self.session: 数据库会话
            parser: 文件解析器实例，负责将文件内容解析成文本块列表
            collection_uid: 目标集合 ID
            file_content: 文档文件内容
            filename: 文档文件名，网络爬取时传入 url 的最后一部分
            source: 文档来源，local_file 或 web_scrape

        Returns:
            SourceItemRead 模型，包含文档基本信息
        """
        logger.info(f"处理并存入文档 '{filename}'，来源：{source}")

        # 获取 collection
        collection_res = await self.session.execute(
            select(Source).where(Source.uid == collection_uid)
        )
        collection = collection_res.scalar_one_or_none()
        if not collection:
            logger.error(f"未找到 collection_uid={collection_uid} 对应的集合")
            raise ValueError(f"Collection with uid {collection_uid} does not exist")

        # 检查文件是否已处理过（通过 file_hash 判断）
        # TODO: 可以考虑按照文件大小，控制是否需要扔到线程池中运行
        file_hash = calculate_file_hash(file_content)

        is_duplicate = await self.session.execute(
            select(1)
            .where(
                SourceItem.item_hash == file_hash,
                SourceItem.source_id == collection.id,
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
            self.vector_db.upsert_documents,
            collection_name=collection.collection_name,
            documents=documents,
            hash_key=file_hash,
        )

        # 写入文档数据
        new_document = SourceItem(
            filename=filename,
            source=source,
            file_hash=file_hash,
            vector_collection_id=collection.id,
        )
        self.session.add(new_document)
        await self.session.flush()

        logger.info(f"文档 '{filename}' 已处理并存储，文本块数量：{stored_count}")
        return SourceItemRead.model_validate(new_document)

    async def get_related_documents(
        self,
        *,
        collection_uid: str,
        query_text: str,
        top_k: int = 5,
    ) -> list[VectorQueryItem]:
        """
        获取 collection_uid 对应向量集合，
        并执行向量库查询，返回与 query_text 相关文档内容
        """
        logger.info(
            f"进行向量库查询，collection_uid={collection_uid}, query_text='{query_text[:50]}', top_k={top_k}"
        )
        result = await self.session.execute(
            select(Source.collection_name).where(
                Source.uid == collection_uid,
            )
        )
        collection_name = result.scalar_one_or_none()

        if not collection_name:
            raise ValueError(
                f"Can not find vector collection for collection_uid={collection_uid}"
            )

        # 执行向量库查询，获取相关文档
        return await asyncio.to_thread(
            self.vector_db.query,
            collection_name=collection_name,
            query_text=query_text,
            top_k=top_k,
        )

    async def process_and_store_document(self, file_path: str) -> None:
        """处理文档并存储到数据库中"""

        # 1. 解析文档内容
        parser = self.file_parser_factory.generate(file_type=Path(file_path).suffix)
        # TODO: 存在同步文件读取，需要改成异步
        parsed_doc: ParsedDocument = await asyncio.to_thread(
            parser.parse, file_input=Path(file_path).read_bytes(), filename=file_path
        )

        # 2. 文档分块
        chunks: list[TextChunk] = await self.text_splitter.split_text(
            text=parsed_doc.text,
            file_path=file_path,
        )

        # 3. FTS 分词
        chunk_texts = [c.content for c in chunks]
        tokens_list: list[str] = await asyncio.to_thread(
            self._batch_tokenize_for_fts, chunk_texts
        )

        # 4. embedding
        embeddings: list[NDArray[np.float32]] = await asyncio.to_thread(
            self.embedding.embed_documents, chunk_texts
        )

        # 5. DB 写入
        await self._save_chunks_to_db()

        # ChromaDB 写入
        await asyncio.to_thread(
            self.vector_db.add_data_to_collection,
            collection=collection_name,
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
        )
