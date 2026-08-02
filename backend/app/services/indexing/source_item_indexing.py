import asyncio
import time
import uuid
from typing import AsyncIterable
from pathlib import Path
from dataclasses import dataclass, asdict

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from loguru import logger

from . import DocumentChunkIndexWriter

from app.rag import (
    VectorDatabase,
    TextSplitter,
    EmbeddingProvider,
    FTSProvider,
)
from app.ingestion import ParsedDocument, ParsedSection
from app.ingestion.parser import FileParserFactory
from app.storage import FileStorage
from app.db.models import Source, SourceItem
from app.db.schemas import DocumentContentInternal
from app.crud import SourceCRUD
from app.api.schemas import IngestPausedResponse, RAGSyncCounters, RAGSyncEvent
from app.core.constants import (
    SourceItemProcessStatus,
    IngestStage,
    RAGSyncEventType,
    SourceType,
)
from app.core.exceptions import DocumentPausedException


# 最大并发量
RAG_INGEST_MAX_CONCURRENCY = 5


@dataclass
class WorkerDone:
    """worker 完成对象；用于内部控制并发流程"""

    source_item_uid: str


class SourceItemIndexingService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        file_storage: FileStorage,
        file_parser_factory: FileParserFactory,
        vector_db: VectorDatabase,
        text_splitter: TextSplitter,
        embedding: EmbeddingProvider,
        fts_provider: FTSProvider,
    ):
        """具体的参数由依赖注入"""
        self.session_factory = session_factory  # worker 内部自己创建 session，避免跨线程/协程共享 session 导致的问题
        self.file_storage = file_storage
        self.file_parser_factory = file_parser_factory
        self.vector_db = vector_db
        self.text_splitter = text_splitter
        self.embedding = embedding
        self.fts_provider = fts_provider

    def _new_document_index_service(
        self, source_crud: SourceCRUD
    ) -> DocumentChunkIndexWriter:
        """
        内部创建 document_index service；
        每个 worker 使用一个单独的实例，避免依赖注入的 session 跨线程/协程共享问题
        """
        return DocumentChunkIndexWriter(
            source_crud=source_crud,
            vector_db=self.vector_db,
            text_splitter=self.text_splitter,
            embedding=self.embedding,
            fts_provider=self.fts_provider,
        )

    async def request_pause_ingest(
        self,
        *,
        source_crud: SourceCRUD,
        source: Source,
        source_items: list[SourceItem],
    ) -> list[IngestPausedResponse]:
        """批量请求暂停文档处理。"""
        # TODO (important!): 由于 sqlite 写锁存在，
        # 现有的 pause 有较大的锁死风险，属于危险操作
        processing_uids = [
            item.uid
            for item in source_items
            if item.status == SourceItemProcessStatus.PROCESSING
        ]
        if processing_uids:
            await source_crud.bulk_update_source_items_status(
                source=source,
                source_item_uids=processing_uids,
            )
            logger.bind(
                event="rag.ingest.pause_requested",
                source_uid=source.uid,
                source_item_count=len(processing_uids),
            ).info("Document ingest pause requested")
        elif source_items:
            logger.bind(
                source_uid=source.uid,
                source_item_count=len(source_items),
            ).warning("No running document ingest found to pause")

        # 返回所有请求暂停的 source_items 的状态
        responses = []
        for item in source_items:
            # NOTE: 这里没有实时查询数据库获取最新状态，
            # 而是基于 source_item 初始状态进行的推断，
            # 可能存在不一致问题
            if item.uid in processing_uids:
                responses.append(
                    IngestPausedResponse(
                        source_uid=source.uid,
                        source_item_uid=item.uid,
                        process_status=SourceItemProcessStatus.PAUSE_REQUESTED,
                        message="Ingest pause requested, waiting for checkpoint",
                    )
                )
                continue

            responses.append(
                IngestPausedResponse(
                    source_uid=source.uid,
                    source_item_uid=item.uid,
                    process_status=item.status,  # 返回当前状态
                    message="No running ingest to pause",
                )
            )

        return responses

    async def resume_source_items(
        self,
        *,
        source_uid: str,
        source_item_uids: list[str],
    ) -> AsyncIterable[RAGSyncEvent]:
        """基于 UID 恢复文档处理，适合后台 job 使用。"""
        async for event in self.ingest_source_items(
            source_uid=source_uid,
            source_item_uids=source_item_uids,
            allowed_statuses=[SourceItemProcessStatus.PAUSED],
        ):
            yield event

    async def ingest_source_items(
        self,
        *,
        source_uid: str,
        source_item_uids: list[str],
        allowed_statuses: list[SourceItemProcessStatus] | None = None,
    ) -> AsyncIterable[RAGSyncEvent]:
        """处理文档并存储到数据库中"""
        ingest_log = logger.bind(source_uid=source_uid)
        ingest_log.bind(
            event="rag.ingest.started",
            source_item_count=len(source_item_uids),
        ).info("Document ingest run started")
        queue: asyncio.Queue[RAGSyncEvent | WorkerDone] = asyncio.Queue()
        semaphore = asyncio.Semaphore(RAG_INGEST_MAX_CONCURRENCY)

        # 输出开始事件
        yield RAGSyncEvent(
            event=RAGSyncEventType.SYNC_START,
            source_uid=source_uid,
            ingest_stage=IngestStage.LOADING,
            sync_progress=0.0,
            message="Document ingestion started",
        )

        async def worker(source_item_uid: str) -> None:
            """单个文档 ingest worker"""
            async with semaphore:
                with logger.contextualize(
                    source_uid=source_uid,
                    source_item_uid=source_item_uid,
                ):
                    try:
                        async for event in self._process_single_document(
                            source_uid=source_uid,
                            source_item_uid=source_item_uid,
                            allowed_statuses=allowed_statuses,
                        ):
                            await queue.put(event)
                    finally:
                        await queue.put(WorkerDone(source_item_uid=source_item_uid))

        # 启动 worker 处理文档
        tasks = [asyncio.create_task(worker(uid)) for uid in source_item_uids]
        completed = 0
        # 统计不同状态的文档数量
        counters = RAGSyncCounters()

        try:
            # 等待 worker 处理完成，同时输出事件
            while completed < len(source_item_uids):
                event = await queue.get()

                if isinstance(event, WorkerDone):
                    completed += 1
                    continue

                if event.event == RAGSyncEventType.ITEM_COMPLETED:
                    counters.completed += 1
                    counters.indexed += 1
                elif event.event == RAGSyncEventType.ITEM_PAUSED:
                    counters.paused += 1
                elif event.event == RAGSyncEventType.ITEM_FAILED:
                    counters.failed += 1
                elif event.event == RAGSyncEventType.ITEM_SKIPPED:
                    counters.skipped += 1

                yield event
        finally:
            # 如果 yield event 阶段发生异常（例如前端关闭连接）
            # 这里需要确保所有后台任务能够正确结束，防止资源泄漏
            # 强制取消所有未完成的 worker 任务
            for task in tasks:
                if not task.done():
                    task.cancel()

            await asyncio.gather(*tasks, return_exceptions=True)

        ingest_log.bind(
            event="rag.ingest.completed",
            completed_count=counters.completed,
            failed_count=counters.failed,
        ).info("Document ingest run completed")

        # 发送处理队列结束事件
        yield RAGSyncEvent(
            event=RAGSyncEventType.SYNC_COMPLETE,
            source_uid=source_uid,
            ingest_stage=IngestStage.COMPLETED,
            sync_progress=1.0,
            counters=counters,
            message="Document ingest run completed",
        )

    async def _process_single_document(
        self,
        *,
        source_uid: str,
        source_item_uid: str,
        allowed_statuses: list[SourceItemProcessStatus] | None = None,
    ) -> AsyncIterable[RAGSyncEvent]:
        """处理单个文档的完整流程，返回处理进度事件的异步生成器"""
        # NOTE: document_ingest 内部创建 AsyncSession，避免跨线程/协程共享 session 导致的问题
        async with self.session_factory() as session:
            source_crud = SourceCRUD(session)
            document_index_service = self._new_document_index_service(source_crud)

            try:
                (
                    source,
                    source_item,
                    should_process,
                ) = await self._resolve_source_and_item(
                    source_crud=source_crud,
                    source_uid=source_uid,
                    source_item_uid=source_item_uid,
                    allowed_statuses=allowed_statuses,
                )
                await session.commit()

                if not should_process:
                    yield RAGSyncEvent(
                        event=RAGSyncEventType.ITEM_SKIPPED,
                        source_uid=source.uid,
                        source_item_uid=source_item.uid,
                        source_item_status=source_item.status,
                        ingest_stage=IngestStage.SKIPPED,
                        message=f"Document skipped due to status: {source_item.status}",
                    )
                    return

                item_started_at = time.perf_counter()
                logger.bind(event="rag.ingest.item.started").info(
                    "Document ingest started"
                )

                # 0.1 暂停请求检查
                await self._pause_checkpoint(source_item_id=source_item.id)

                # 1.0 发送开始事件
                yield RAGSyncEvent(
                    event=RAGSyncEventType.ITEM_PROGRESS,
                    source_uid=source.uid,
                    source_item_uid=source_item.uid,
                    source_item_status=SourceItemProcessStatus.PROCESSING,
                    ingest_stage=IngestStage.LOADING,
                    item_progress=0.01,
                    message="Loading document",
                )

                if not source_item.document_content:
                    # 发送文档解析事件
                    yield RAGSyncEvent(
                        event=RAGSyncEventType.ITEM_PROGRESS,
                        source_uid=source.uid,
                        source_item_uid=source_item.uid,
                        source_item_status=SourceItemProcessStatus.PROCESSING,
                        ingest_stage=IngestStage.PARSING,
                        item_progress=0.15,
                        message="Parsing document",
                    )

                # 1.1 获取解析后的对象
                content_source = (
                    "cached" if source_item.document_content is not None else "parsed"
                )
                parsed_doc = await self._ensure_parsed_document(
                    source_crud=source_crud,
                    source=source,
                    source_item=source_item,
                )
                logger.bind(
                    content_source=content_source,
                ).info("Document content prepared")
                # 解析内容落库后先提交，避免分块/向量化期间长期持有 SQLite 写锁。
                await session.commit()

                # 1.2 暂停请求检查
                await self._pause_checkpoint(source_item_id=source_item.id)

                # 2. 处理解析结果，进行分块、FTS 分词、向量化并入库
                async for event in document_index_service.index_parsed_document(
                    source=source,
                    source_item=source_item,
                    parsed_doc=parsed_doc,
                    checkpoint=lambda: self._pause_checkpoint(
                        source_item_id=source_item.id
                    ),
                ):
                    yield event

                # 2.1 检查 pause 前提交事务，确保数据的完整性
                await session.commit()
                await self._pause_checkpoint(source_item_id=source_item.id)

                # 3. 胜利宣言
                await self._mark_item_status(
                    session=session,
                    source_crud=source_crud,
                    source_item=source_item,
                    status=SourceItemProcessStatus.COMPLETED,
                )
                logger.bind(
                    event="rag.ingest.item.completed",
                    duration_ms=round(
                        (time.perf_counter() - item_started_at) * 1000,
                        3,
                    ),
                ).info("Document ingest completed")

                # 单个文档完成事件
                yield RAGSyncEvent(
                    event=RAGSyncEventType.ITEM_COMPLETED,
                    source_uid=source.uid,
                    source_item_uid=source_item.uid,
                    source_item_status=SourceItemProcessStatus.COMPLETED,
                    ingest_stage=IngestStage.COMPLETED,
                    item_progress=1.0,
                    message="Document ingest completed",
                )

            except DocumentPausedException:
                # 暂停应该确保文档处理被提交
                await session.commit()

                yield RAGSyncEvent(
                    event=RAGSyncEventType.ITEM_PAUSED,
                    source_uid=source_uid,
                    source_item_uid=source_item_uid,
                    source_item_status=SourceItemProcessStatus.PAUSED,
                    ingest_stage=IngestStage.PAUSED,
                    message="Document ingest paused",
                )
            except Exception as exc:
                error_id = uuid.uuid4().hex
                logger.bind(
                    event="rag.ingest.item.failed",
                    error_id=error_id,
                ).opt(exception=exc).error("Document ingest failed")

                try:
                    await session.commit()
                except Exception:
                    # 避免是由于 session 本身异常
                    await session.rollback()

                # 确保 source_item 被绑定
                refetched_item = (
                    await source_crud.get_source_item_by_uid_for_source_uid(
                        source_uid=source_uid, item_uid=source_item_uid
                    )
                )
                if refetched_item:
                    await self._mark_item_status(
                        session=session,
                        source_crud=source_crud,
                        source_item=refetched_item,
                        status=SourceItemProcessStatus.FAILED,
                    )

                yield RAGSyncEvent(
                    event=RAGSyncEventType.ITEM_FAILED,
                    source_uid=source_uid,
                    source_item_uid=source_item_uid,
                    source_item_status=SourceItemProcessStatus.FAILED,
                    ingest_stage=IngestStage.FAILED,
                    message="Document ingest failed",
                    error="Document ingest failed",
                    error_id=error_id,
                )

    async def _resolve_source_and_item(
        self,
        *,
        source_crud: SourceCRUD,
        source_uid: str,
        source_item_uid: str,
        allowed_statuses: list[SourceItemProcessStatus] | None = None,
    ) -> tuple[Source, SourceItem, bool]:
        """声明占用 source_item，并返回 source/source_item"""
        # 声明占用 source_item，通过数据库锁机制，确保只有一次请求能够 claim 到 source_item
        should_process = await source_crud.claim_source_item_for_ingest(
            source_uid=source_uid,
            source_item_uid=source_item_uid,
            allowed_statuses=allowed_statuses,
        )  # NOTE: claim 操作并不能保证数据存在

        if not should_process:
            # claim 失败，不进行带有 document_content 的查询，
            # 通过轻量级查询 source, source_item 的状态，触发后续的跳过逻辑
            result = await source_crud.get_source_and_item_by_uid(
                source_uid=source_uid,
                source_item_uid=source_item_uid,
            )
            if not result:
                raise ValueError(
                    f"Source or SourceItem not found for uid: {source_uid}, {source_item_uid}"
                )
            source, source_item = result

            skipped_log = logger.bind(
                source_item_status=source_item.status.value,
            )
            if allowed_statuses:
                skipped_log.warning("Document resume skipped due to current status")
            else:
                skipped_log.info("Document ingest skipped due to current status")
            return source, source_item, False

        # 查询完整数据
        result = await source_crud.get_source_and_item_with_content_by_uid(
            source_uid=source_uid,
            source_item_uid=source_item_uid,
        )
        # 确保数据存在
        if not result:
            raise ValueError(
                f"Source or SourceItem not found for uid: {source_uid}, {source_item_uid}"
            )
        source, source_item = result
        return source, source_item, True

    async def _ensure_parsed_document(
        self,
        *,
        source_crud: SourceCRUD,
        source: Source,
        source_item: SourceItem,
    ) -> ParsedDocument:
        """
        加载或解析文档内容，确保基于 source_item 构建对应的 ParsedDocument 对象

        检查规则：
        - 已有 DocumentContent: 直接恢复 ParsedDocument 对象
        - LOCAL_FILE 且缺少 DocumentContent: 解析文件内容构建 ParsedDocument 对象
        - 其它 SourceType: 需要确保在进入 ingest 之前，构建完整的 DocumentContent
        """
        # 检查是否已经解析过文件
        if source_item.document_content:
            metadata = source_item.document_content.metadata_json or {}
            return ParsedDocument(
                text=source_item.document_content.content,
                title=source_item.title,
                source_type=source.source_type,
                # 恢复 sections, page_boundaries
                sections=self._restore_sections(metadata),
                page_boundaries=self._restore_page_boundaries(metadata),
            )

        if source.source_type != SourceType.LOCAL_FILE:
            raise ValueError(
                f"Source item {source_item.uid} has no materialized document content; "
                f"run source materialization before indexing"
            )

        # 构建 LOCAL_FILE 类型的 ParsedDocument 对象
        parsed_doc = await self._parse_local_file_source_item(
            source_item=source_item,
        )

        # ParsedDocument 入库操作
        await source_crud.upsert_document_content(
            source_item=source_item,
            content_data=DocumentContentInternal(
                content=parsed_doc.text,
                metadata_json={
                    # TODO: metadata 后续使用类型严格约束
                    "sections": [
                        asdict(section) for section in parsed_doc.sections or []
                    ],
                    "page_boundaries": parsed_doc.page_boundaries or [],
                },
            ),
        )

        return parsed_doc

    async def _parse_local_file_source_item(
        self,
        *,
        source_item: SourceItem,
    ) -> ParsedDocument:
        """LOCAL_FILE 类型调用：解析文件并构建 ParsedDocument 对象"""
        if not source_item.storage_key:
            raise ValueError("Local file source item requires storage_key")
        if not source_item.filename:
            raise ValueError("Local file source item requires filename")

        # 解析文档内容
        file_bytes = await self.file_storage.load_file(key=source_item.storage_key)
        # 暂停断点
        await self._pause_checkpoint(source_item_id=source_item.id)

        parser = self.file_parser_factory.generate(
            file_type=Path(source_item.filename).suffix.lower()
        )
        return await asyncio.to_thread(
            parser.parse,
            file_input=file_bytes,
            filename=source_item.filename,
        )

    async def _mark_item_status(
        self,
        *,
        session: AsyncSession,
        source_crud: SourceCRUD,
        source_item: SourceItem,
        status: SourceItemProcessStatus,
    ) -> None:
        """更新 SourceItem 状态的通用方法"""
        await source_crud.update_source_item_status(source_item, status)
        await session.commit()

    def _restore_sections(self, metadata: dict) -> list[ParsedSection] | None:
        """从 DocumentContent metadata 中恢复章节信息"""
        sections = metadata.get("sections") or []
        if not sections:
            return None
        return [ParsedSection(**section) for section in sections]

    def _restore_page_boundaries(self, metadata: dict) -> list[tuple[int, int]] | None:
        """从 DocumentContent metadata 中恢复分页边界"""
        boundaries = metadata.get("page_boundaries") or []
        if not boundaries:
            return None
        return [(int(start), int(end)) for start, end in boundaries]

    async def _pause_checkpoint(self, *, source_item_id: int) -> None:
        """暂停检查点"""
        paused_uid: str | None = None

        # NOTE: _pause_checkpoint 创建独立的 session,
        # 确保数据库读取到的状态是最新的
        async with self.session_factory() as session:
            source_crud = SourceCRUD(session)
            source_item = await source_crud.get_source_item_by_id(source_item_id)

            if not source_item:
                raise ValueError("Source item not found")

            if source_item.status == SourceItemProcessStatus.PAUSE_REQUESTED:
                # 更新状态为 PAUSED，触发暂停事件
                await self._mark_item_status(
                    session=session,
                    source_crud=source_crud,
                    source_item=source_item,
                    status=SourceItemProcessStatus.PAUSED,
                )
                paused_uid = source_item.uid

        # 在 session 上下文之外 raise DocumentPausedException，
        # 避免 session 内部异常，导致 PAUSED 状态未正确提交到数据库
        if paused_uid:
            logger.bind(
                event="rag.ingest.item.paused",
                source_item_uid=paused_uid,
            ).info("Document ingest paused")
            raise DocumentPausedException(
                f"Document {paused_uid} paused by user request"
            )
