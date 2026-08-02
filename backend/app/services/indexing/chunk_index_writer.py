import asyncio
from typing import AsyncIterable
from typing import Callable, Awaitable
import uuid

import numpy as np
from loguru import logger
from numpy.typing import NDArray

from app.rag import (
    VectorDatabase,
    TextChunk,
    TextSplitter,
    EmbeddingProvider,
    FTSProvider,
)
from app.ingestion import ParsedDocument, ParsedSection
from app.db.models import Source, SourceItem
from app.db.schemas import DocumentChunkInternal
from app.crud import SourceCRUD
from app.api.schemas import RAGSyncEvent
from app.utils import calculate_text_hash
from app.core.constants import SourceItemProcessStatus, IngestStage, RAGSyncEventType


# 文档分块后每批次的数量
EMBEDDING_BATCH_SIZE = 50
# vector_id 使用 UUIDv5 生成
RAG_NAMESPACE = uuid.UUID("2fbcbf86-2bb8-4c0c-92b7-c8a4840dbff4")  # 专属命名空间

# 暂停检查点类型定义
PauseCheckPoint = Callable[[], Awaitable[None]]


def generate_vector_id(source_item_id: int, chunk_index: int) -> str:
    """基于 UUIDv5 生成向量 ID"""
    name = f"{source_item_id}_{chunk_index}"
    return str(uuid.uuid5(RAG_NAMESPACE, name))


class DocumentChunkIndexWriter:
    def __init__(
        self,
        *,
        source_crud: SourceCRUD,
        vector_db: VectorDatabase,
        text_splitter: TextSplitter,
        embedding: EmbeddingProvider,
        fts_provider: FTSProvider,
    ):
        """具体的参数由依赖注入"""
        self.source_crud = source_crud
        self.vector_db = vector_db
        self.text_splitter = text_splitter
        self.embedding = embedding
        self.fts_provider = fts_provider

    async def index_parsed_document(
        self,
        *,
        source: Source,
        source_item: SourceItem,
        parsed_doc: ParsedDocument,
        checkpoint: PauseCheckPoint | None = None,
    ) -> AsyncIterable[RAGSyncEvent]:
        """处理单个文档的完整流程，返回处理进度事件的异步生成器"""

        async def maybe_checkpoint() -> None:
            if checkpoint:
                await checkpoint()

        # 2.0 发送分块事件
        yield RAGSyncEvent(
            event=RAGSyncEventType.ITEM_PROGRESS,
            source_uid=source.uid,
            source_item_uid=source_item.uid,
            ingest_stage=IngestStage.SPLITTING,
            source_item_status=SourceItemProcessStatus.PROCESSING,
            item_progress=0.3,
            message="Splitting document into chunks",
        )

        # 2.1 文档分块
        chunks: list[TextChunk] = await self.text_splitter.split_text(
            text=parsed_doc.text, file_path=source_item.filename or ""
        )
        logger.bind(
            chunk_count=len(chunks),
        ).info("Document split into chunks")
        if not chunks:
            logger.warning("Document produced no indexable chunks")

        # 2.2 暂停请求检查
        await maybe_checkpoint()

        # 3.0 发送分块处理事件
        yield RAGSyncEvent(
            event=RAGSyncEventType.ITEM_PROGRESS,
            source_uid=source.uid,
            source_item_uid=source_item.uid,
            ingest_stage=IngestStage.PROCESSING_CHUNKS,
            source_item_status=SourceItemProcessStatus.PROCESSING,
            item_progress=0.5,
            message="Processing document chunks",
        )

        # 3.1 批处理前预处理数据库记录
        await self._prepare_reindex_source(source=source, source_item=source_item)

        # 3.2 批处理
        async for event in self._process_chunks_in_batch(
            source=source,
            source_item=source_item,
            chunks=chunks,
            parsed_doc=parsed_doc,
            maybe_checkpoint=maybe_checkpoint,
        ):
            # 传递 event
            yield event

    def _batch_tokenize_for_fts(self, texts: list[str]) -> list[str]:
        """批量 FTS 分词同步函数"""
        return [self.fts_provider.tokenize_for_index(text) for text in texts]

    async def _process_chunks_in_batch(
        self,
        source: Source,
        source_item: SourceItem,
        chunks: list[TextChunk],
        parsed_doc: ParsedDocument,
        maybe_checkpoint: PauseCheckPoint,
    ) -> AsyncIterable[RAGSyncEvent]:
        """批处理文本的 FTS 分词、向量化嵌入以及数据库写入"""

        batches = [
            chunks[i : i + EMBEDDING_BATCH_SIZE]
            for i in range(0, len(chunks), EMBEDDING_BATCH_SIZE)
        ]

        for batch_index, batch_chunks in enumerate(batches):
            # 3.2.0 暂停请求检查
            await maybe_checkpoint()

            chunk_texts = [chunk.content for chunk in batch_chunks]
            batch_log = logger.bind(
                batch=f"{batch_index + 1}/{len(batches)}",
            )

            # 3.2.1 FTS 分词
            chunk_tokens: list[str] = await asyncio.to_thread(
                self._batch_tokenize_for_fts, chunk_texts
            )
            batch_log.debug("Chunk FTS tokenization completed")

            # 3.2.2 embedding
            embeddings: list[NDArray[np.float32]] = await asyncio.to_thread(
                self.embedding.embed_documents, chunk_texts
            )
            batch_log.debug("Chunk embeddings generated")

            # 3.2.3 构建 SQL 记录
            rows: list[DocumentChunkInternal] = []
            for offset, chunk in enumerate(batch_chunks):
                chunk_index = batch_index * EMBEDDING_BATCH_SIZE + offset
                section = self._resolve_chunk_section(chunk, parsed_doc)

                rows.append(
                    DocumentChunkInternal(
                        source_item_id=source_item.id,
                        vector_id=generate_vector_id(
                            source_item_id=source_item.id, chunk_index=chunk_index
                        ),
                        chunk_index=chunk_index,
                        chunk_hash=calculate_text_hash(chunk.content),
                        chunk_content=chunk.content,
                        chunk_tokens=chunk_tokens[offset],
                        chunk_pos=chunk.pos,
                        # TODO: 保留字段；后续再具体实现相关逻辑
                        page_number=self._resolve_page_number(chunk, parsed_doc),
                        section_header=section.header if section else None,
                        metadata_json={
                            "anchor": section.anchor,
                            "section_level": section.level,
                            "origin_url": source_item.origin_url,
                        }
                        if section
                        else None,
                    )
                )
            await self.source_crud.bulk_insert_document_chunks(rows)
            batch_log.debug("Document chunks stored")

            # 3.2.4 构建 vector 记录
            await asyncio.to_thread(
                self.vector_db.add_data_to_collection,
                collection_name=source.collection_name,
                ids=[row.vector_id for row in rows],
                embeddings=embeddings,
                metadatas=[
                    {"source_item_id": source_item.id, "chunk_index": row.chunk_index}
                    for row in rows
                ],
            )
            batch_log.debug("Document vectors stored")

            # 3.2.5 发送批次完成事件
            yield RAGSyncEvent(
                event=RAGSyncEventType.ITEM_PROGRESS,
                source_uid=source.uid,
                source_item_uid=source_item.uid,
                ingest_stage=IngestStage.PROCESSING_CHUNKS,
                source_item_status=SourceItemProcessStatus.PROCESSING,
                item_progress=0.5 + (batch_index + 1) / len(batches) * 0.4,
                message=f"Processed chunk batch {batch_index + 1}/{len(batches)}",
            )

    async def _prepare_reindex_source(
        self, source: Source, source_item: SourceItem
    ) -> None:
        """预处理数据库记录，为文档重建索引做准备"""
        # 检索旧向量 ids
        old_vector_ids = await self.source_crud.list_vector_ids_by_source_item_id(
            source_item_id=source_item.id
        )

        # 删除旧向量
        if old_vector_ids:
            await asyncio.to_thread(
                self.vector_db.delete_data_from_collection,
                collection_name=source.collection_name,
                ids=list(old_vector_ids),
            )

        # 删除数据库记录
        await self.source_crud.delete_document_chunks_by_source_item_id(
            source_item_id=source_item.id
        )
        if old_vector_ids:
            logger.bind(
                old_vector_count=len(old_vector_ids),
            ).info("Previous document index cleared")

    def _resolve_chunk_section(
        self, chunk: TextChunk, parsed_doc: ParsedDocument
    ) -> ParsedSection | None:
        """
        解析文档结构信息

        解析逻辑：
        自前向后匹配最后一个 start <= chunk.pos 的 section
        """
        if not parsed_doc.sections:
            return None

        # TODO: 后续这里可以优化
        mactched = None
        for section in parsed_doc.sections:
            if section.start <= chunk.pos:
                mactched = section
            else:
                break

        return mactched

    def _resolve_page_number(
        self, chunk: TextChunk, parsed_doc: ParsedDocument
    ) -> int | None:
        """
        解析分页信息；仅适用于 PDF 等分页文档

        解析逻辑：
        page_boundaries 包含每页的文本边界 (start, end)；
        匹配第一个 start <= chunk.pos < end 的 page，返回对应页码
        """
        if not parsed_doc.page_boundaries:
            return None

        for page_number, (start, end) in enumerate(parsed_doc.page_boundaries, start=1):
            if start <= chunk.pos < end:
                return page_number

        return None
