from typing import AsyncIterable

from loguru import logger

from .ingest_runner import IngestRunService
from .ingest_item_state import IngestItemStateService
from .document_index import DocumentIndexService

from app.ingestion.crawler import WebCrawler, ParsedPage
from app.db.models import Source, SourceItem
from app.db.schemas import WebCrawlConfig, SourceItemInternal
from app.crud import SourceCRUD
from app.api.schemas import IngestProgressEvent, IngestPausedResponse
from app.core.constants import SourceItemProcessStatus, IngestStage, RAGIngestEventType
from app.core.exceptions import DocumentPausedException


# ingest runner 并发控制
WEB_CRAWL_INDEX_MAX_CONCURRENCY = 3


class WebCrawlSyncService:
    def __init__(
        self,
        *,
        source_crud: SourceCRUD,
        crawler: WebCrawler,
        ingest_runner: IngestRunService,
        ingest_item_state_service: IngestItemStateService,
        document_index: DocumentIndexService,
    ):
        self.source_crud = source_crud
        self.crawler = crawler
        self.document_index = document_index
        self.ingest_runner = ingest_runner
        self.ingest_item_state_service = ingest_item_state_service

    async def request_pause_ingest(
        self,
        source: Source,
        source_item: SourceItem,
    ) -> IngestPausedResponse:
        return await self.ingest_item_state_service.request_pause_ingest(
            source=source,
            source_item=source_item,
        )

    async def resume_ingest(
        self,
        source: Source,
        source_item: SourceItem,
    ) -> AsyncIterable[IngestProgressEvent]:
        # await self.ingest_operations.ensure_resumable_item(source_item=source_item)
        ...

    async def crawl_and_ingest(
        self,
        *,
        source: Source,
        config: WebCrawlConfig,
    ) -> AsyncIterable[IngestProgressEvent]:
        """执行爬取和后续 ingest 的流程"""
        # 加载历史爬取元数据
        previous_metadata_by_item_key = await self._load_previous_metadata_by_item_key(
            source=source
        )

        async for event in self.ingest_runner.run_stream_ingest(
            item_stream=self.crawler.crawl(
                config=config,
                previous_metadata_by_item_key=previous_metadata_by_item_key,
            ),
            processor=lambda parsed_page: self._process_crawled_page(
                parsed_page=parsed_page, source=source
            ),
            max_concurrency=WEB_CRAWL_INDEX_MAX_CONCURRENCY,
            start_event=IngestProgressEvent(
                event=RAGIngestEventType.INGEST_START,
                source_uid=source.uid,
                ingest_stage=IngestStage.LOADING,
                process_status=SourceItemProcessStatus.PROCESSING,
                item_progress=0.0,
                message="Web crawl sync started",
            ),
            complete_event=IngestProgressEvent(
                event=RAGIngestEventType.INGEST_COMPLETE,
                source_uid=source.uid,
                ingest_stage=IngestStage.COMPLETED,
                process_status=SourceItemProcessStatus.COMPLETED,
                message="Web crawl sync completed",
                item_progress=1.0,
            ),
            on_error=lambda item, exc: self._handle_crawled_page_exception(
                source, item, exc
            ),
        ):
            yield event

    async def _process_crawled_page(
        self, *, parsed_page: ParsedPage, source: Source
    ) -> AsyncIterable[IngestProgressEvent]:
        """处理爬取到的页面，执行后续的文档分块、索引等流程，返回处理进度事件的异步生成器"""
        # 0. 尝试获取已存在的 source_item
        existing_item = await self.source_crud.get_source_item_by_item_key(
            source=source, item_key=parsed_page.item_key
        )

        # 0.1 如果已经存在 source_item -> 判断对应 html 页面是否有变化
        if existing_item and self._is_unchanged(
            existing_item=existing_item, parsed_page=parsed_page
        ):
            # 文档已存在并且未改变，跳过处理
            logger.info(
                f"SourceItem with item_key {parsed_page.item_key} already exists and is unchanged, skipping"
            )
            await self._update_checked_metadata(
                source=source, source_item=existing_item, parsed_page=parsed_page
            )
            # 响应跳过事件
            yield self._skipped_event(
                source=source,
                source_item=existing_item,
                message="Web page unchanged, skipped indexing",
            )

        # 1. 基于 parsed_page 更新或构建 source_item
        source_item = await self.source_crud.upsert_source_item_by_item_key(
            source=source,
            item_data=SourceItemInternal(
                item_key=parsed_page.item_key,
                title=parsed_page.parsed_document.title,
                origin_url=parsed_page.origin_url,
                item_hash=parsed_page.parsed_markdown_hash,
                metadata_json=parsed_page.fetch_metadata,
            ),
        )

        # 1.1 标记 source_item 状态
        await self.ingest_item_state_service.mark_processing(source_item=source_item)

        # 1.2 暂停检查点
        await self.ingest_item_state_service.pause_checkpoint(
            source_item_id=source_item.id
        )

        yield IngestProgressEvent(
            event=RAGIngestEventType.INGEST_PROGRESS,
            source_uid=source.uid,
            source_item_uid=source_item.uid,
            ingest_stage=IngestStage.PARSING,
            process_status=SourceItemProcessStatus.PROCESSING,
            item_progress=0.15,
            message="Web page parsed",
        )

        # 2. 调用 document_index 服务处理文档内容，生成索引
        async for event in self.document_index.index_parsed_document(
            source=source,
            source_item=source_item,
            parsed_doc=parsed_page.parsed_document,
            cover_content=True,
            checkpoint=lambda: self.ingest_item_state_service.pause_checkpoint(
                source_item_id=source_item.id
            ),
        ):
            yield event

        # 3. 完成文档处理，更新状态并发送完成事件
        await self.ingest_item_state_service.mark_completed(source_item=source_item)
        yield IngestProgressEvent(
            event=RAGIngestEventType.INGEST_PROGRESS,
            source_uid=source.uid,
            source_item_uid=source_item.uid,
            ingest_stage=IngestStage.COMPLETED,
            process_status=SourceItemProcessStatus.COMPLETED,
            item_progress=1.0,
            message="Web page ingest completed",
        )

    async def _handle_crawled_page_exception(
        self, source: Source, parsed_page: ParsedPage, exc: Exception
    ) -> AsyncIterable[IngestProgressEvent]:
        """异常处理回调函数；处理 index 过程中的异常"""
        source_item = await self.source_crud.get_source_item_by_item_key(
            source=source, item_key=parsed_page.item_key
        )

        if isinstance(exc, DocumentPausedException):
            # 处理用户主动暂停的情况，更新状态并发送事件
            yield IngestProgressEvent(
                event=RAGIngestEventType.ITEM_PAUSED,
                source_uid=source.uid,
                source_item_uid=source_item.uid if source_item else None,
                ingest_stage=IngestStage.PAUSED,
                process_status=SourceItemProcessStatus.PAUSED,
                message="Web page ingest paused",
            )
            return

        logger.error(f"Error processing web page {parsed_page.item_key}: {exc}")

        if source_item:
            # 更新状态为失败
            await self.ingest_item_state_service.mark_failed(source_item=source_item)

        yield IngestProgressEvent(
            event=RAGIngestEventType.ITEM_FAILED,
            source_uid=source.uid,
            source_item_uid=source_item.uid if source_item else None,
            ingest_stage=IngestStage.FAILED,
            process_status=SourceItemProcessStatus.FAILED,
            message="Web page ingest failed",
            error=str(exc),
        )

    async def _load_previous_metadata_by_item_key(
        self, source: Source
    ) -> dict[str, dict]:
        """加载指定 source 的历史爬取元数据"""
        source_items = await self.source_crud.list_source_items_by_source_id(
            source_id=source.id,
            limit=10_000,  # NOTE: 这里会一次性加载所有的 source_item
            offset=0,
        )
        # 将 source_item.metadata_json 转换为 item_key -> metadata 的字典
        return {
            item.item_key: item.metadata_json or {}
            for item in source_items
            if item.metadata_json
        }

    async def _is_unchanged(
        self, *, existing_item: SourceItem, parsed_page: ParsedPage
    ) -> bool:
        """判断爬取到的页面是否与已存在的 source_item 对应的页面相同"""
        return existing_item.item_hash == parsed_page.parsed_markdown_hash

    async def _update_checked_metadata(
        self, *, source: Source, source_item: SourceItem, parsed_page: ParsedPage
    ) -> None:
        """更新 source_item 的现有字段"""
        await self.source_crud.upsert_source_item_by_item_key(
            source=source,
            item_data=SourceItemInternal(
                item_key=parsed_page.item_key,
                title=source_item.title,
                filename=source_item.filename,
                origin_url=source_item.origin_url,
                item_hash=source_item.item_hash,
                metadata_json={
                    **(source_item.metadata_json or {}),
                    **parsed_page.fetch_metadata,
                },
            ),
        )

    def _skipped_event(
        self,
        *,
        source: Source,
        source_item: SourceItem,
        message: str,
    ) -> IngestProgressEvent:
        """构建跳过事件"""
        return IngestProgressEvent(
            event=RAGIngestEventType.ITEM_SKIPPED,
            source_uid=source.uid,
            source_item_uid=source_item.uid,
            ingest_stage=IngestStage.SKIPPED,
            process_status=source_item.status,
            message=message,
        )
