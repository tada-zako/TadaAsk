import asyncio
from typing import AsyncIterable, cast
from pathlib import Path

from loguru import logger

from .ingest_operations import IngestOperationsService
from .document_index import DocumentIndexService

from app.ingestion import ParsedDocument
from app.ingestion.parser import FileParserFactory
from app.storage import FileStorage
from app.db.models import Source, SourceItem
from app.crud import SourceCRUD
from app.api.schemas import IngestProgressEvent, IngestPausedResponse
from app.core.constants import SourceItemProcessStatus, IngestStage, RAGIngestEventType


# 最大并发量
RAG_INGEST_MAX_CONCURRENCY = 5


class DocumentIngestService:
    def __init__(
        self,
        *,
        source_crud: SourceCRUD,
        file_storage: FileStorage,
        file_parser_factory: FileParserFactory,
        ingest_operations: IngestOperationsService,
        document_index: DocumentIndexService,
    ):
        """具体的参数由依赖注入"""
        self.source_crud = source_crud
        self.file_storage = file_storage
        self.file_parser_factory = file_parser_factory
        self.ingest_operations = ingest_operations
        self.document_index = document_index

    async def request_pause_ingest(
        # NOTE: 这里的 source_item 实例传递之前，需要确保对应 source, status 不是完成/PAUSED
        self,
        source: Source,
        source_item: SourceItem,
    ) -> IngestPausedResponse:
        """请求暂停文档处理"""
        return await self.ingest_operations.request_pause_ingest(
            source=source, source_item=source_item
        )

    async def resume_ingest(
        self, source: Source, source_item: SourceItem
    ) -> AsyncIterable[IngestProgressEvent]:
        """恢复文档处理"""
        # 仅允许从 PAUSED 状态恢复
        await self.ingest_operations.ensure_resumable(source_item=source_item)

        # 主动触发后续 ingest
        async for event in self.ingest_source_items(
            source=source, source_items=[source_item]
        ):
            yield event

    async def ingest_source_items(
        self, source: Source, source_items: list[SourceItem]
    ) -> AsyncIterable[IngestProgressEvent]:
        """处理文档并存储到数据库中"""

        async for event in self.ingest_operations.run_ingest(
            source=source,
            source_items=source_items,
            processor=self._process_single_document,
            max_concurrency=RAG_INGEST_MAX_CONCURRENCY,
        ):
            yield event

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
        await self.ingest_operations.pause_checkpoint(source_item.id)

        # 1.0 发送开始事件
        yield IngestProgressEvent(
            event=RAGIngestEventType.INGEST_PROGRESS,
            source_uid=source.uid,
            source_item_uid=source_item.uid,
            ingest_stage=IngestStage.LOADING,
            process_status=SourceItemProcessStatus.PROCESSING,
            item_progress=0.01,
            message="Loading document",
        )

        # 1.1 检查是否已经解析过文件
        # 这里的 document_content 字段在 Depends 中提前加载到 SourceItem；
        # 后续如果 ingest 业务流程并发量较大，耗时较长，
        # 需要改成按需加载的方式，避免并发情况下数据不一致
        if source_item.document_content:
            parsed_doc = ParsedDocument(
                text=source_item.document_content.content,
                title=source_item.title,
                source_type=source.source_type,
                sections=None,  # TODO: sections 字段可以从 document_content.metadata_json 中恢复
                metadata=source_item.document_content.metadata_json,
            )
        else:
            if not source_item.storage_key:
                raise ValueError("Local file source item requires storage_key")

            # 1.2 解析文档内容
            file_bytes = await self.file_storage.load_file(key=source_item.storage_key)
            # 1.3 暂停断点
            await self.ingest_operations.pause_checkpoint(source_item.id)

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
            filename = cast(
                str, source_item.filename
            )  # DocumentIngestService 中确保 filename 存在

            parser = self.file_parser_factory.generate(
                file_type=Path(filename).suffix.lower()
            )
            parsed_doc: ParsedDocument = await asyncio.to_thread(
                parser.parse,
                file_input=file_bytes,
                filename=filename,
            )

        # 2. 处理解析结果，进行分块、FTS 分词、向量化并入库
        async for event in self.document_index.index_parsed_document(
            source=source,
            source_item=source_item,
            parsed_doc=parsed_doc,
            cover_content=source_item.document_content
            is None,  # 只有在之前没有解析过的情况下才入库内容
        ):
            yield event

        # 3. 调用完成
        yield await self.ingest_operations.complete_item(
            source=source,
            source_item=source_item,
            message="Document ingest completed",
        )
