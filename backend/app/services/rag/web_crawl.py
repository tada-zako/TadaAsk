from typing import AsyncIterable

from app.api.schemas import IngestProgressEvent, IngestPausedResponse
from app.core.constants import IngestStage, RAGIngestEventType, SourceItemProcessStatus
from app.crud import SourceCRUD
from app.db.models import Source, SourceItem
from app.ingestion.crawler.models import ParsedPage
from app.services.rag.document_index import DocumentIndexService
from app.services.rag.ingest_operations import IngestOperationsService
from app.utils.calcu_file_hash import calculate_text_hash


class WebCrawlSyncService:
    def __init__(
        self,
        *,
        source_crud: SourceCRUD,
        crawler,  # TODO: WebCrawler facade: config -> discovered/fetched/parsed pages
        document_index: DocumentIndexService,
        ingest_operations: IngestOperationsService,
    ):
        self.source_crud = source_crud
        self.crawler = crawler
        self.document_index = document_index
        self.ingest_operations = ingest_operations

    async def request_pause_ingest(
        self,
        source: Source,
        source_item: SourceItem,
    ) -> IngestPausedResponse:
        return await self.ingest_operations.request_pause_ingest(
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
