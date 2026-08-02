import asyncio
import time
import uuid
from dataclasses import asdict, dataclass
from typing import AsyncIterable, cast

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ingestion.crawler import (
    WebCrawler,
    ParsedPage,
    HTMLPageParser,
    DiscoveredURL,
    FetchedPage,
    WebPageMetadata,
)
from app.db.models import Source, SourceItem
from app.db.schemas import WebCrawlConfig, SourceItemInternal, DocumentContentInternal
from app.crud import SourceCRUD
from app.rag import VectorDatabase
from app.api.schemas import RAGSyncCounters, RAGSyncEvent
from app.core.constants import (
    CrawlEntryType,
    SourceItemProcessStatus,
    IngestStage,
    RAGSyncEventType,
    SourceType,
)


# ingest runner 并发控制
WEB_CRAWL_INDEX_MAX_CONCURRENCY = 5

# 处于 index 构建状态集合；crawl_sync 过程不能修改这些状态的 source_items
_INDEX_BUSY_STATUSES = {
    SourceItemProcessStatus.PROCESSING,
    SourceItemProcessStatus.PAUSE_REQUESTED,
    SourceItemProcessStatus.PAUSED,
}


@dataclass
class CrawlWorkerDone:
    """crawl worker 完成信号，用于避免失败 worker 导致主循环等待。"""


@dataclass(frozen=True)
class StaleSourceItemRef:
    """待清理的历史 source item 轻量引用。"""

    id: int
    uid: str
    item_key: str
    status: SourceItemProcessStatus


@dataclass(frozen=True)
class SourceRef:
    """
    后台任务使用的 source 轻量引用，避免跨 session 持有 ORM 对象
    NOTE:
        使用该 ref 是由于 WebCrawlSyncService.sync_source() 内部并不直接操作 Source 对象，
        实际只有启动时的状态确认和 source.uid 的使用；使用 ref 可以减轻内部 IO 压力；
        但是需要注意，sync_source() 内部会导致 source 数据改变，
        如果后续需要直接使用 source 对象，需要确保避免状态不一致问题。
    """

    id: int
    uid: str
    collection_name: str
    source_type: SourceType


class WebCrawlSyncService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        crawler: WebCrawler,
        html_parser: HTMLPageParser,
        vector_db: VectorDatabase,
    ):
        self.session_factory = session_factory
        self.crawler = crawler
        self.html_parser = html_parser
        self.vector_db = vector_db

    async def sync_source(
        self,
        *,
        source_uid: str,
        config: WebCrawlConfig,
    ) -> AsyncIterable[RAGSyncEvent]:
        """
        Web Crawl sync 流程；

        负责的业务：
        - discover URL
        - fetch page
        - parse HTML -> ParsedDocument
        - upsert SourceItem
        - upsert DocumentContent
        - 标记需要 Index 的 SourceItem，并修改 status 为 PENDING
        """
        counters = RAGSyncCounters()
        changed_source_item_uids: list[str] = []
        started_at = time.perf_counter()

        source_ref = await self._load_web_crawl_source_ref(source_uid=source_uid)
        crawl_log = logger.bind(source_uid=source_ref.uid)
        crawl_log.bind(
            event="rag.web_crawl.started",
            crawl_entry_type=config.entry_type.value,
        ).info("Web crawl materialization started")

        # 0. 发送开始事件
        yield RAGSyncEvent(
            event=RAGSyncEventType.SYNC_START,
            source_uid=source_ref.uid,
            ingest_stage=IngestStage.DISCOVERING,
            sync_progress=0.0,
            message="Web crawl materialization started",
        )

        # 1.0 加载历史爬取元数据
        previous_metadata_by_item_key = await self._load_previous_metadata_by_item_key(
            source_ref=source_ref
        )

        # 1.1 discover URL
        discovered_urls = await self.crawler.discover_urls(config=config)
        discovered_item_keys = {discovered.item_key for discovered in discovered_urls}
        counters.discovered = len(discovered_urls)
        crawl_log.bind(
            discovered_count=counters.discovered,
        ).info("Web crawl discovery completed")

        if not discovered_urls:
            crawl_log.warning("Web crawl discovered no URLs")
            crawl_log.bind(
                event="rag.web_crawl.completed",
                discovered_count=0,
                duration_ms=round((time.perf_counter() - started_at) * 1000, 3),
            ).info("Web crawl materialization completed")
            yield RAGSyncEvent(
                event=RAGSyncEventType.SYNC_COMPLETE,
                source_uid=source_ref.uid,
                ingest_stage=IngestStage.COMPLETED,
                sync_progress=1.0,
                counters=counters,
                message=("no URLs discovered with the given configuration"),
            )
            return

        # 1.2 依次发送 discover 事件
        for discovered in discovered_urls:
            yield RAGSyncEvent(
                event=RAGSyncEventType.ITEM_DISCOVERED,
                source_uid=source_ref.uid,
                ingest_stage=IngestStage.DISCOVERING,
                message=f"Discovered URL: {discovered.discovered_url}",
                counters=counters,
            )

        # 2.0 依次 fetch 页面
        queue: asyncio.Queue[
            RAGSyncEvent | ParsedPage | FetchedPage | CrawlWorkerDone
        ] = asyncio.Queue()
        semaphore = asyncio.Semaphore(WEB_CRAWL_INDEX_MAX_CONCURRENCY)
        crawl_log.bind(
            page_count=len(discovered_urls),
            concurrency=WEB_CRAWL_INDEX_MAX_CONCURRENCY,
        ).info("Fetching and parsing discovered web pages")

        # 2.1 定义 fetch worker
        async def worker(discovered: DiscoveredURL) -> None:
            async with semaphore:
                try:
                    result = await self._fetch_and_parse_page(
                        discovered=discovered,
                        config=config,
                        previous_metadata=previous_metadata_by_item_key.get(
                            discovered.item_key
                        ),
                    )
                    await queue.put(result)
                except Exception as exc:
                    # 抓取或解析失败，记录日志并发送失败事件
                    counters.failed += 1
                    error_id = uuid.uuid4().hex
                    logger.bind(
                        event="rag.web_crawl.page.failed",
                        error_id=error_id,
                    ).opt(exception=exc).error("Web page crawl failed")

                    await queue.put(
                        RAGSyncEvent(
                            event=RAGSyncEventType.ITEM_FAILED,
                            source_uid=source_ref.uid,
                            ingest_stage=IngestStage.FAILED,
                            message=f"Failed to crawl page: {discovered.discovered_url}",
                            error="Web page crawl failed",
                            error_id=error_id,
                            counters=counters,
                        )
                    )
                finally:
                    await queue.put(CrawlWorkerDone())

        # 2.2 创建 fetch worker 任务队列
        with logger.contextualize(source_uid=source_ref.uid):
            tasks = [asyncio.create_task(worker(url)) for url in discovered_urls]
        completed_workers = 0
        processed_results = 0

        # 3.0 处理 worker 结果
        try:
            while completed_workers < len(discovered_urls):
                result = await queue.get()

                if isinstance(result, CrawlWorkerDone):
                    # worker 任务完成
                    completed_workers += 1
                    continue

                if isinstance(result, RAGSyncEvent):
                    # 输出 fetch/parse 过程中的事件
                    yield result
                    continue

                processed_results += 1

                # 处理成功 fetch + parse 的页面
                synced_uid = await self._sync_crawled_page(
                    result=result,
                    source_ref=source_ref,
                    counters=counters,
                )

                # 计算 progress 数值
                sync_progress = processed_results / len(discovered_urls) - 0.2

                if synced_uid:
                    changed_source_item_uids.append(synced_uid)

                    # 发送进度事件
                    yield RAGSyncEvent(
                        event=RAGSyncEventType.ITEM_UPSERTED,
                        source_uid=source_ref.uid,
                        source_item_uid=synced_uid,
                        source_item_status=SourceItemProcessStatus.PENDING,
                        ingest_stage=IngestStage.UPSERTING,
                        sync_progress=sync_progress,
                        message="Web page materialized; indexing required",
                        counters=counters,
                    )
                    continue

                # 发送页面跳过事件
                yield RAGSyncEvent(
                    event=RAGSyncEventType.ITEM_SKIPPED,
                    source_uid=source_ref.uid,
                    ingest_stage=IngestStage.SKIPPED,
                    sync_progress=sync_progress,
                    message=f"Web page unchanged or skipped: {result.discovered_url}",
                    counters=counters,
                )

        finally:
            # 取消所有未完成的任务
            for task in tasks:
                if not task.done():
                    task.cancel()

            await asyncio.gather(*tasks, return_exceptions=True)

        crawl_log.bind(
            upserted_count=counters.upserted,
            failed_count=counters.failed,
        ).info("Web page materialization phase completed")

        # 4. 清理本轮不再属于 URL 列表的历史 source_items，避免旧索引继续进入 RAG。
        async for cleanup_event in self._cleanup_stale_source_items(
            source_ref=source_ref,
            config=config,
            discovered_item_keys=discovered_item_keys,
            counters=counters,
        ):
            yield cleanup_event

        crawl_log.bind(
            event="rag.web_crawl.completed",
            upserted_count=counters.upserted,
            failed_count=counters.failed,
        ).info("Web crawl materialization completed")

        # 5. 发送完成事件
        yield RAGSyncEvent(
            event=RAGSyncEventType.SYNC_COMPLETE,
            source_uid=source_ref.uid,
            ingest_stage=IngestStage.COMPLETED,
            sync_progress=1.0,
            counters=counters,
            message=(
                "Web crawl materialization completed; "
                f"{len(changed_source_item_uids)} item(s) require indexing; "
                f"{counters.pruned} stale item(s) pruned"
            ),
        )

    async def _fetch_and_parse_page(
        self,
        *,
        discovered: DiscoveredURL,
        config: WebCrawlConfig,
        previous_metadata: WebPageMetadata | None,
    ) -> ParsedPage | FetchedPage:
        """抓取并解析页面内容"""
        # 抓取页面内容
        async with self.crawler.create_http_client() as client:
            fetched_page = await self.crawler.fetch_page(
                client=client,
                discovered=discovered,
                config=config,
                previous_metadata=previous_metadata,
            )

        # 如果抓取的 page 未变化
        if fetched_page.not_modified:
            return fetched_page

        # 处理 config 中的 extraction 规则
        options = self.crawler.resolve_extraction_options(
            config=config, url=discovered.discovered_url
        )

        # 解析 HTML 页面并返回
        return await asyncio.to_thread(
            self.html_parser.parse,
            page=fetched_page,
            options=options,
        )

    async def _sync_crawled_page(
        self,
        *,
        source_ref: SourceRef,
        result: ParsedPage | FetchedPage,
        counters: RAGSyncCounters,
    ) -> str | None:
        """
        基于爬取结果同步到数据库，并返回需要后续 index 的 source_item_uid。
        如果页面未变化或被跳过（例如处于 index 阶段），则返回 None。

        同步规则：
        - 如果 source_item 不存在，则创建新的 source_item，并标记为 PENDING
        - 如果抓取结果为 304，则更新 metadata 并跳
        - 如果 source_item 正在 indexing 阶段， 则跳过修改，避免内容和索引不一致
        - 如果 source_item 存在且页面未修改，则更新 metadata 并跳过 COMPLETED 状态的 source_item；对于其他状态的 source_item，更新状态为 PENDING
        - 如果 source_item 存在且页面已修改，则更新内容和 metadata，并标记为 PENDING
        """
        async with self.session_factory() as session:
            async with session.begin():
                source_crud = SourceCRUD(session)
                return await self._sync_crawled_page_with_crud(
                    source_crud=source_crud,
                    source=cast(Source, source_ref),
                    result=result,
                    counters=counters,
                )

    async def _sync_crawled_page_with_crud(
        self,
        *,
        source_crud: SourceCRUD,
        source: Source,
        result: ParsedPage | FetchedPage,
        counters: RAGSyncCounters,
    ) -> str | None:
        """在当前短事务内同步单个抓取结果。"""
        existing_item = await source_crud.get_source_item_by_item_key(
            source=source,
            item_key=result.item_key,
        )

        # 不存在 source_item 情况
        if not existing_item:
            parsed_page = cast(
                ParsedPage, result
            )  # 类型断言，确保 result 是 ParsedPage

            # 创建新 source_item，并标记为需要 index
            source_item = await source_crud.upsert_source_item_by_item_key(
                source=source,
                item_data=SourceItemInternal(
                    item_key=parsed_page.item_key,
                    title=parsed_page.parsed_document.title,
                    filename=None,
                    storage_key=None,
                    origin_url=parsed_page.discovered_url,
                    item_hash=parsed_page.parsed_markdown_hash,
                    metadata_json=asdict(parsed_page.fetch_metadata),
                    status=SourceItemProcessStatus.PENDING,
                ),
            )
            # 创建 DocumentContent
            await source_crud.upsert_document_content(
                source_item=source_item,
                content_data=DocumentContentInternal(
                    content=parsed_page.parsed_document.text,
                    metadata_json={
                        "sections": [
                            asdict(section)
                            for section in parsed_page.parsed_document.sections or []
                        ],
                        "page_boundaries": parsed_page.parsed_document.page_boundaries
                        or [],
                    },
                ),
            )

            counters.upserted += 1
            return source_item.uid

        # fetched 页面 304 未修改情况
        if isinstance(result, FetchedPage) and result.not_modified:
            # 更新 checked metadata
            await self._update_checked_metadata(
                source_crud=source_crud,
                source=source,
                source_item=existing_item,
                extra_metadata=WebPageMetadata(
                    etag=result.etag,
                    last_modified=result.last_modified,
                    last_fetch_status=result.status_code,
                    content_type=result.content_type,
                ),
            )
            counters.skipped += 1
            return None

        parsed_page = cast(ParsedPage, result)  # 类型断言，确保 result 是 ParsedPage

        # 如果目标 source_item 正在 index 中，跳过修改
        if existing_item and existing_item.status in _INDEX_BUSY_STATUSES:
            logger.bind(
                source_item_uid=existing_item.uid,
                source_item_status=existing_item.status.value,
            ).warning("Web page materialization skipped because item is busy")
            counters.skipped += 1
            return None

        # 存在 source_item，但页面内容未修改，更新 metadata 并跳过
        if existing_item.item_hash == parsed_page.parsed_markdown_hash:
            # 更新 checked metadata
            await self._update_checked_metadata(
                source_crud=source_crud,
                source=source,
                source_item=existing_item,
                extra_metadata=WebPageMetadata(
                    etag=parsed_page.fetch_metadata.etag,
                    last_modified=parsed_page.fetch_metadata.last_modified,
                    last_fetch_status=parsed_page.fetch_metadata.last_fetch_status,
                    content_type=parsed_page.fetch_metadata.content_type,
                ),
            )

            # 跳过 COMPLETED 状态的 source_item
            if existing_item.status == SourceItemProcessStatus.COMPLETED:
                counters.skipped += 1
                return None

            # 对于其他状态的 source_item，更新状态为 PENDING
            await source_crud.update_source_item_status(
                source_item=existing_item,
                new_status=SourceItemProcessStatus.PENDING,
            )
            counters.upserted += 1
            return existing_item.uid

        # 处理页面内容发生变化的 source_item
        await source_crud.upsert_source_item_by_item_key(
            source=source,
            item_data=SourceItemInternal(
                item_key=parsed_page.item_key,
                title=parsed_page.parsed_document.title,
                filename=None,
                storage_key=None,
                origin_url=parsed_page.discovered_url,
                item_hash=parsed_page.parsed_markdown_hash,
                metadata_json=asdict(parsed_page.fetch_metadata),
                status=SourceItemProcessStatus.PENDING,
            ),
        )
        # 更新 DocumentContent
        await source_crud.upsert_document_content(
            source_item=existing_item,
            content_data=DocumentContentInternal(
                content=parsed_page.parsed_document.text,
                # metadata_json 后续通过明确类型定义声明
                metadata_json={
                    "sections": [
                        asdict(section)
                        for section in parsed_page.parsed_document.sections or []
                    ],
                    "page_boundaries": parsed_page.parsed_document.page_boundaries
                    or [],
                },
            ),
        )

        counters.upserted += 1
        return existing_item.uid

    async def _cleanup_stale_source_items(
        self,
        *,
        source_ref: SourceRef,
        config: WebCrawlConfig,
        discovered_item_keys: set[str],
        counters: RAGSyncCounters,
    ) -> AsyncIterable[RAGSyncEvent]:
        """
        清理本轮未发现的历史网页项。

        当前只对 url_list 开启硬删除；
        后续扩展 sitemap/site_root 需要先确认 discovery 完整
        且未被 max_pages 截断，再开放清理逻辑
        """
        if config.entry_type != CrawlEntryType.URL_LIST:
            # 跳过暂不支持类型
            return

        # 加载所有旧 source_items
        stale_items = await self._load_stale_source_items(
            source_ref=source_ref,
            discovered_item_keys=discovered_item_keys,
        )
        if not stale_items:
            return

        pruned_before = counters.pruned
        cleanup_failed_before = counters.cleanup_failed
        logger.bind(
            source_uid=source_ref.uid,
            stale_item_count=len(stale_items),
        ).info("Pruning stale web pages")

        for stale_item in stale_items:
            if stale_item.status in _INDEX_BUSY_STATUSES:
                # 忙状态，跳过
                counters.skipped += 1
                logger.bind(
                    source_uid=source_ref.uid,
                    source_item_uid=stale_item.uid,
                    source_item_status=stale_item.status.value,
                ).warning("Stale web page pruning skipped because item is busy")
                yield RAGSyncEvent(
                    event=RAGSyncEventType.ITEM_SKIPPED,
                    source_uid=source_ref.uid,
                    source_item_uid=stale_item.uid,
                    source_item_status=stale_item.status,
                    ingest_stage=IngestStage.SKIPPED,
                    sync_progress=0.9,
                    counters=counters,
                    message=(
                        "Stale web page cleanup skipped because item is busy: "
                        f"{stale_item.item_key}"
                    ),
                )
                continue

            try:
                (
                    deleted_vector_count,
                    vector_cleanup_error_id,
                ) = await self._delete_stale_source_item(
                    source_ref=source_ref,
                    stale_item=stale_item,
                )
            except Exception as exc:
                counters.cleanup_failed += 1
                error_id = uuid.uuid4().hex
                logger.bind(
                    event="rag.web_crawl.prune.failed",
                    error_id=error_id,
                    source_uid=source_ref.uid,
                    source_item_uid=stale_item.uid,
                ).opt(exception=exc).error("Stale web page pruning failed")
                yield RAGSyncEvent(
                    event=RAGSyncEventType.ITEM_FAILED,
                    source_uid=source_ref.uid,
                    source_item_uid=stale_item.uid,
                    source_item_status=stale_item.status,
                    ingest_stage=IngestStage.FAILED,
                    sync_progress=0.9,
                    counters=counters,
                    message=f"Failed to prune stale web page: {stale_item.item_key}",
                    error="Stale web page pruning failed",
                    error_id=error_id,
                )
                continue

            counters.pruned += 1
            if vector_cleanup_error_id:
                counters.cleanup_failed += 1

            # 传输清理操作事务
            yield RAGSyncEvent(
                event=RAGSyncEventType.ITEM_DELETED,
                source_uid=source_ref.uid,
                source_item_uid=stale_item.uid,
                ingest_stage=IngestStage.PRUNING,
                sync_progress=0.9,
                counters=counters,
                message=(
                    "Pruned stale web page source item: "
                    f"{stale_item.item_key}; removed {deleted_vector_count} vector(s)"
                ),
                error=(
                    "Stale web page vector cleanup failed"
                    if vector_cleanup_error_id
                    else None
                ),
                error_id=vector_cleanup_error_id,
            )

        logger.bind(
            source_uid=source_ref.uid,
            pruned_count=counters.pruned - pruned_before,
            cleanup_failed_count=counters.cleanup_failed - cleanup_failed_before,
        ).info("Stale web page pruning completed")

    async def _load_stale_source_items(
        self,
        *,
        source_ref: SourceRef,
        discovered_item_keys: set[str],
    ) -> list[StaleSourceItemRef]:
        """
        加载本轮 URL 列表中已经不存在的历史 source items;
        转换为 StaleSourceItemRef 结构对象，避免在 session 外直接操作 ORM 对象
        """
        async with self.session_factory() as session:
            source_crud = SourceCRUD(session)
            source_items = await source_crud.list_source_items_not_in_item_keys(
                source_id=source_ref.id,
                item_keys=discovered_item_keys,
            )

        return [
            # 转换为 StaleSourceItemRef 对象
            StaleSourceItemRef(
                id=item.id,
                uid=item.uid,
                item_key=item.item_key,
                status=item.status,
            )
            for item in source_items
        ]

    async def _delete_stale_source_item(
        self,
        *,
        source_ref: SourceRef,
        stale_item: StaleSourceItemRef,
    ) -> tuple[int, str | None]:
        """删除 stale item 的数据库记录，并尽力清理对应向量。"""
        async with self.session_factory() as session:
            async with session.begin():
                source_crud = SourceCRUD(session)
                vector_ids = list(
                    await source_crud.list_vector_ids_by_source_item_id(
                        source_item_id=stale_item.id
                    )
                )
                # 删除数据库记录
                deleted = await source_crud.delete_source_item_by_id(
                    item_id=stale_item.id
                )
                if not deleted:
                    raise ValueError(f"Source item not found: {stale_item.uid}")

        if not vector_ids:
            return 0, None

        try:
            # 删除向量数据库中对应的向量数据
            await asyncio.to_thread(
                self.vector_db.delete_data_from_collection,
                collection_name=source_ref.collection_name,
                ids=vector_ids,
            )
        except Exception as exc:
            # DB 已删除，RAG 不会再召回该 item；
            # 向量残留单独记录，后续增加可重试或全量重建兜底逻辑
            error_id = uuid.uuid4().hex
            logger.bind(
                event="rag.web_crawl.vector_cleanup.failed",
                error_id=error_id,
                source_uid=source_ref.uid,
                source_item_uid=stale_item.uid,
            ).opt(exception=exc).warning("Stale web page vector cleanup failed")
            return len(vector_ids), error_id

        return len(vector_ids), None

    async def _load_previous_metadata_by_item_key(
        self, source_ref: SourceRef
    ) -> dict[str, WebPageMetadata]:
        """加载指定 source 的历史爬取元数据"""
        async with self.session_factory() as session:
            source_crud = SourceCRUD(session)
            source_items = await source_crud.list_source_items_by_source_id(
                source_id=source_ref.id,
                limit=10_000,  # NOTE: 这里会一次性加载所有的 source_item
                offset=0,
            )

        # 将 source_item.metadata_json 转换为 item_key -> metadata 的字典
        return {
            item.item_key: WebPageMetadata.from_dict(item.metadata_json)
            for item in source_items
        }

    async def _load_web_crawl_source_ref(self, *, source_uid: str) -> SourceRef:
        """加载 source 轻量引用，并确认类型为 Web Crawl。"""
        async with self.session_factory() as session:
            source_crud = SourceCRUD(session)
            source = await source_crud.get_source_by_uid(source_uid=source_uid)
            if not source:
                raise ValueError(f"Source not found: {source_uid}")
            if source.source_type != SourceType.WEB_CRAWL:
                raise ValueError("Source type does not support web crawl sync")
            return SourceRef(
                id=source.id,
                uid=source.uid,
                collection_name=source.collection_name,
                source_type=source.source_type,
            )

    async def _update_checked_metadata(
        self,
        *,
        source_crud: SourceCRUD,
        source: Source,
        source_item: SourceItem,
        extra_metadata: WebPageMetadata,
    ) -> SourceItem:
        """更新 source_item 的现有字段"""
        metadata = {
            **(source_item.metadata_json or {}),
            **asdict(extra_metadata),
        }

        return await source_crud.upsert_source_item_by_item_key(
            source=source,
            item_data=SourceItemInternal(
                item_key=source_item.item_key,
                title=source_item.title,
                filename=source_item.filename,
                storage_key=source_item.storage_key,
                origin_url=source_item.origin_url,
                item_hash=source_item.item_hash,
                metadata_json=metadata,
            ),
        )
