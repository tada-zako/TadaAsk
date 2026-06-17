import asyncio
from typing import AsyncIterable, cast
import uuid
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from loguru import logger

from app.rag import (
    VectorDatabase,
    TextChunk,
    TextSplitter,
    EmbeddingProvider,
    FTSProvider,
)
from app.ingestion import ParsedDocument
from app.ingestion.parser import FileParserFactory
from app.storage import FileStorage
from app.db.models import Source, SourceItem
from app.db.schemas import DocumentChunkInternal
from app.crud import SourceCRUD
from app.api.schemas import IngestProgressEvent, IngestPausedResponse
from app.utils.calcu_file_hash import calculate_text_hash
from app.core.constants import SourceItemProcessStatus, IngestStage, RAGIngestEventType
from app.core.exceptions import DocumentPausedException


# 最大并发量
RAG_INGEST_MAX_CONCURRENCY = 5
# 文档分块后每批次的数量
EMBEDDING_BATCH_SIZE = 50
# vector_id 使用 UUIDv5 生成
RAG_NAMESPACE = uuid.UUID("2fbcbf86-2bb8-4c0c-92b7-c8a4840dbff4")  # 专属命名空间


def generate_vector_id(source_item_id: int, chunk_index: int) -> str:
    """基于 UUIDv5 生成向量 ID"""
    name = f"{source_item_id}_{chunk_index}"
    return str(uuid.uuid5(RAG_NAMESPACE, name))


class DocumentIngestService:
    def __init__(
        self,
        *,
        source_crud: SourceCRUD,
        file_storage: FileStorage,
        vector_db: VectorDatabase,
        text_splitter: TextSplitter,
        embedding: EmbeddingProvider,
        fts_provider: FTSProvider,
        file_parser_factory: FileParserFactory,
    ):
        """具体的参数由依赖注入"""
        self.source_crud = source_crud
        self.file_storage = file_storage
        self.vector_db = vector_db
        self.text_splitter = text_splitter
        self.embedding = embedding
        self.fts_provider = fts_provider
        self.file_parser_factory = file_parser_factory

    def _batch_tokenize_for_fts(self, texts: list[str]) -> list[str]:
        """批量 FTS 分词同步函数"""
        return [self.fts_provider.tokenize_for_index(text) for text in texts]

    async def request_pause_ingest(
        # NOTE: 这里的 source_item 实例传递之前，需要确保对应 source, status 不是完成/PAUSED
        self,
        source: Source,
        source_item: SourceItem,
    ) -> IngestPausedResponse:
        """请求暂停文档处理"""
        if source_item.status != SourceItemProcessStatus.PROCESSING:
            logger.warning(
                f"SourceItem {source_item.uid} 状态为 {source_item.status}，无法暂停"
            )
            return IngestPausedResponse(
                source_uid=source.uid,
                source_item_uid=source_item.uid,
                process_status=source_item.status,
                message="No running ingest to pause",
            )

        # 更新数据库状态，等待处理流程检查点生效
        await self.source_crud.update_source_item_status(
            source_item, SourceItemProcessStatus.PAUSE_REQUESTED
        )
        logger.info(
            f"SourceItem {source_item.uid} 已标记为 PAUSE_REQUESTED，等待处理流程检查点生效"
        )
        return IngestPausedResponse(
            source_uid=source.uid,
            source_item_uid=source_item.uid,
            process_status=SourceItemProcessStatus.PAUSE_REQUESTED,
            message="Ingest pause requested, waiting for checkpoint",
        )

    async def resume_ingest(
        self, source: Source, source_item: SourceItem
    ) -> AsyncIterable[IngestProgressEvent]:
        """恢复文档处理"""
        # 仅允许从 PAUSED 状态恢复
        if source_item.status != SourceItemProcessStatus.PAUSED:
            logger.warning(
                f"SourceItem {source_item.uid} 状态为 {source_item.status}，无法恢复"
            )
            raise ValueError(
                f"SourceItem {source_item.uid} is not in PAUSED status, cannot resume"
            )

        # 主动触发后续 ingest
        async for event in self.ingest_source_items(
            source=source, source_items=[source_item]
        ):
            yield event

    async def _pause_checkpoint(self, source_item_id: int) -> None:
        """处理流程中的暂停检查点；在关键步骤前调用，检查是否有暂停请求"""
        result = await self.source_crud.get_source_item_by_id(source_item_id)
        item = cast(SourceItem, result)  # 内部调用；能够确保结果存在

        if item.status == SourceItemProcessStatus.PAUSE_REQUESTED:
            # 更新状态为 PAUSED，触发暂停事件
            await self.source_crud.update_source_item_status(
                item, SourceItemProcessStatus.PAUSED
            )
            logger.info(f"SourceItem {item.uid} 已更新状态为 PAUSED，触发暂停")
            # 主动触发暂停事件
            raise DocumentPausedException(f"Document {item.uid} paused by user request")

    async def _process_single_document(
        self, source: Source, source_item: SourceItem
    ) -> AsyncIterable[IngestProgressEvent]:
        """处理单个文档的完整流程，返回处理进度事件的异步生成器"""

        if source_item.status not in [
            SourceItemProcessStatus.PENDING,
            SourceItemProcessStatus.PAUSED,
            SourceItemProcessStatus.FAILED,
        ]:
            logger.warning(
                f"SourceItem {source_item.uid} 状态为 {source_item.status}，不执行处理"
            )
            yield IngestProgressEvent(
                event=RAGIngestEventType.ITEM_SKIPPED,
                source_uid=source.uid,
                source_item_uid=source_item.uid,
                ingest_stage=IngestStage.SKIPPED,
                process_status=source_item.status,
                message=f"Document skipped due to status: {source_item.status}",
            )
            return

        # 0. 更新 item 状态
        await self.source_crud.update_source_item_status(
            source_item, SourceItemProcessStatus.PROCESSING
        )

        # 0.1 暂停请求检查
        await self._pause_checkpoint(source_item.id)

        # 1.0 发送开始事件
        yield IngestProgressEvent(
            event=RAGIngestEventType.INGEST_PROGRESS,
            source_uid=source.uid,
            source_item_uid=source_item.uid,
            ingest_stage=IngestStage.LOADING,
            process_status=SourceItemProcessStatus.PROCESSING,
            item_progress=0.01,
            message="Document ingest started",
        )

        # 1.1 解析文档内容
        file_bytes = await self.file_storage.load_file(key=source_item.storage_key)

        # 暂停断点
        await self._pause_checkpoint(source_item.id)

        # 1.2 检查是否已经解析过文件
        # 这里的 document_content 字段在 Depends 中提前加载到 SourceItem；
        # 后续如果 ingest 业务流程并发量较大，耗时较长，
        # 需要改成按需加载的方式，避免并发情况下数据不一致
        if source_item.document_content:
            markdown_text = source_item.document_content.content
            parsed_metadata = {}  # 不重复载入
        else:
            yield IngestProgressEvent(
                event=RAGIngestEventType.INGEST_PROGRESS,
                source_uid=source.uid,
                source_item_uid=source_item.uid,
                ingest_stage=IngestStage.PARSING,
                process_status=SourceItemProcessStatus.PROCESSING,
                item_progress=0.15,
                message="Parsing document",
            )

            # 1.3 解析文档内容
            parser = self.file_parser_factory.generate(
                file_type=Path(source_item.filename).suffix.lower()
            )
            parsed_doc: ParsedDocument = await asyncio.to_thread(
                parser.parse,
                file_input=file_bytes,
                filename=source_item.filename,
            )

            markdown_text = parsed_doc.text
            # TODO: 文档 metadata 处理逻辑暂不确定
            parsed_metadata = {}

            # 1.4 解析结果入库
            await self.source_crud.upsert_document_content(
                source_item=source_item, content=markdown_text
            )

        # 1.5 暂停请求检查
        await self._pause_checkpoint(source_item.id)

        # 2.0 发送分块事件
        yield IngestProgressEvent(
            event=RAGIngestEventType.INGEST_PROGRESS,
            source_uid=source.uid,
            source_item_uid=source_item.uid,
            ingest_stage=IngestStage.SPLITTING,
            process_status=SourceItemProcessStatus.PROCESSING,
            item_progress=0.3,
            message="Splitting document into chunks",
        )

        # 2.1 文档分块
        chunks: list[TextChunk] = await self.text_splitter.split_text(
            text=markdown_text, file_path=source_item.filename
        )

        # 2.2 暂停请求检查
        await self._pause_checkpoint(source_item.id)

        # 3.0 发送分块处理事件
        yield IngestProgressEvent(
            event=RAGIngestEventType.INGEST_PROGRESS,
            source_uid=source.uid,
            source_item_uid=source_item.uid,
            ingest_stage=IngestStage.PROCESSING_CHUNKS,
            process_status=SourceItemProcessStatus.PROCESSING,
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
            parsed_metadata=parsed_metadata,
        ):
            # 传递 event
            yield event

        # 6 胜利宣言
        await self.source_crud.update_source_item_status(
            source_item, SourceItemProcessStatus.COMPLETED
        )
        yield IngestProgressEvent(
            event=RAGIngestEventType.INGEST_PROGRESS,
            source_uid=source.uid,
            source_item_uid=source_item.uid,
            ingest_stage=IngestStage.COMPLETED,
            process_status=SourceItemProcessStatus.COMPLETED,
            item_progress=1.0,
            message="Document ingest completed successfully",
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

    async def _process_chunks_in_batch(
        self,
        source: Source,
        source_item: SourceItem,
        chunks: list[TextChunk],
        parsed_metadata: dict,
    ) -> AsyncIterable[IngestProgressEvent]:
        """批处理文本的 FTS 分词、向量化嵌入以及数据库写入"""

        batches = [
            chunks[i : i + EMBEDDING_BATCH_SIZE]
            for i in range(0, len(chunks), EMBEDDING_BATCH_SIZE)
        ]

        for batch_index, batch_chunks in enumerate(batches):
            # 3.2.0 暂停请求检查
            await self._pause_checkpoint(source_item.id)

            chunk_texts = [chunk.content for chunk in batch_chunks]

            # 3.2.1 FTS 分词
            chunk_tokens: list[str] = await asyncio.to_thread(
                self._batch_tokenize_for_fts, chunk_texts
            )

            # 3.2.2 embedding
            embeddings: list[NDArray[np.float32]] = await asyncio.to_thread(
                self.embedding.embed_documents, chunk_texts
            )

            # 3.2.3 构建 SQL 记录
            rows = []
            for offset, chunk in enumerate(batch_chunks):
                chunk_index = batch_index * EMBEDDING_BATCH_SIZE + offset
                vector_id = generate_vector_id(
                    source_item_id=source_item.id, chunk_index=chunk_index
                )
                rows.append(
                    DocumentChunkInternal(
                        source_item_id=source_item.id,
                        vector_id=vector_id,
                        chunk_index=chunk_index,
                        chunk_hash=calculate_text_hash(chunk.content),
                        chunk_content=chunk.content,
                        chunk_tokens=chunk_tokens[offset],
                        chunk_pos=chunk.pos,
                        # TODO: 保留字段；后续再具体实现相关逻辑
                        # page_number=self._resolve_page_number(),
                        # section_header=self._resolve_section_header(),
                        # metadata_json=parsed_metadata,
                    )
                )
            await self.source_crud.bulk_insert_document_chunks(rows)

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

            # 3.2.5 发送批次完成事件
            yield IngestProgressEvent(
                event=RAGIngestEventType.INGEST_PROGRESS,
                source_uid=source.uid,
                source_item_uid=source_item.uid,
                ingest_stage=IngestStage.PROCESSING_CHUNKS,
                process_status=SourceItemProcessStatus.PROCESSING,
                item_progress=0.5 + (batch_index + 1) / len(batches) * 0.4,
                message=f"Processed chunk batch {batch_index + 1}/{len(batches)}",
            )

    async def ingest_source_items(
        self, source: Source, source_items: list[SourceItem]
    ) -> AsyncIterable[IngestProgressEvent]:
        """处理文档并存储到数据库中"""

        # 异步并发相关
        queue: asyncio.Queue[IngestProgressEvent] = asyncio.Queue()
        # TODO: 并发控制应该提升到更通用的层面，作为有状态服务的一部分；目前先在这里实现一个简单的 Semaphore 控制并发量
        semaphore = asyncio.Semaphore(RAG_INGEST_MAX_CONCURRENCY)

        completed_workers = 0
        total_items = len(source_items)

        # 发送开始事件
        yield IngestProgressEvent(
            event=RAGIngestEventType.INGEST_START,
            source_uid=source.uid,
            ingest_stage=IngestStage.LOADING,
            process_status=SourceItemProcessStatus.PROCESSING,
            item_progress=0.0,
            message="Document ingestion started",
        )

        async def worker(source_item: SourceItem):
            """单个文档处理 worker"""
            async with semaphore:
                try:
                    async for event in self._process_single_document(
                        source=source,
                        source_item=source_item,
                    ):
                        await queue.put(event)
                except DocumentPausedException:
                    # 触发暂停事件
                    await queue.put(
                        IngestProgressEvent(
                            event=RAGIngestEventType.ITEM_PAUSED,
                            source_uid=source.uid,
                            source_item_uid=source_item.uid,
                            ingest_stage=IngestStage.PAUSED,
                            process_status=SourceItemProcessStatus.PAUSED,
                            message="Document ingest paused",
                        )
                    )

                except Exception as e:
                    # 异常处理
                    logger.error(f"Error processing document {source_item.uid}: {e}")
                    # 更新数据库状态
                    await self.source_crud.update_source_item_status(
                        source_item, SourceItemProcessStatus.FAILED
                    )
                    await queue.put(
                        IngestProgressEvent(
                            event=RAGIngestEventType.ITEM_FAILED,
                            source_uid=source.uid,
                            source_item_uid=source_item.uid,
                            ingest_stage=IngestStage.FAILED,
                            process_status=SourceItemProcessStatus.FAILED,
                            message="Document ingest failed",
                            error=str(e),
                        )
                    )

                finally:
                    # 最终完成
                    await queue.put(
                        IngestProgressEvent(
                            event=RAGIngestEventType._WORKER_DONE,
                            source_uid=source.uid,
                            source_item_uid=source_item.uid,
                            ingest_stage=IngestStage.COMPLETED,
                            process_status=SourceItemProcessStatus.COMPLETED,
                            message="Document ingest completed",
                            item_progress=1.0,
                        )
                    )

        # 启动任务队列
        tasks = [asyncio.create_task(worker(item)) for item in source_items]

        # 监听事件队列
        while completed_workers < total_items:
            event = await queue.get()
            if event.event == RAGIngestEventType._WORKER_DONE:
                completed_workers += 1
                continue  # 内部事件，不发送给前端

            yield event

        await asyncio.gather(*tasks)  # 确保所有任务完成
        yield IngestProgressEvent(
            event=RAGIngestEventType.INGEST_COMPLETE,
            source_uid=source.uid,
            ingest_stage=IngestStage.COMPLETED,
            process_status=SourceItemProcessStatus.COMPLETED,
            message="All documents ingested",
            item_progress=1.0,
        )
