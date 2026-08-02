import asyncio
from dataclasses import dataclass, field

from loguru import logger

from app.core.constants import CrawlEntryType, SourceProcessStatus, SourceType
from app.core.exceptions import (
    SourceCreateConflictError,
    SourceCreateStorageError,
    SourceCreateValidationError,
    SourceDeleteStorageError,
    SourceUpdateConflictError,
    SourceUpdateValidationError,
)
from app.crud import SourceCRUD
from app.db.models import Source
from app.db.schemas import SourceCreate, SourceInternal, SourceUpdate, WebCrawlConfig
from app.rag import VectorDatabase
from app.storage import FileStorage
from app.utils import hostname_from_url, path_prefix_from_url


@dataclass
class SourceDeleteResult:
    """Source 删除结果结构体"""

    deleted_source_item_count: int
    file_deleted_count: int
    file_delete_failed_count: int
    vector_collection_deleted: bool
    cleanup_errors: list[str] = field(default_factory=list)


class SourceService:
    """Source 操作 service。"""

    def __init__(
        self,
        *,
        source_crud: SourceCRUD,
        vector_db: VectorDatabase,
        file_storage: FileStorage,
    ):
        self.source_crud = source_crud
        self.vector_db = vector_db
        self.file_storage = file_storage

    async def create_source(self, source_data: SourceCreate) -> Source:
        """创建数据源，并初始化对应向量集合。"""
        try:
            source_data = self._validate_and_normalize_source_create(source_data)
        except SourceCreateValidationError as exc:
            logger.bind(source_type=source_data.source_type.value).warning(
                "Source creation rejected due to invalid configuration: {}", str(exc)
            )
            raise

        # Source 名称是全局唯一的，提前检查能给前端更清晰的错误。
        existing_source = await self.source_crud.get_source_by_name(
            source_name=source_data.source_name
        )
        if existing_source:
            logger.bind(source_type=source_data.source_type.value).warning(
                "Source creation rejected because the name already exists"
            )
            raise SourceCreateConflictError("source with the same name already exists")

        source_internal = SourceInternal(**source_data.model_dump())

        try:
            # 创建向量集合
            await asyncio.to_thread(
                self.vector_db.create_collection,
                collection_name=source_internal.collection_name,
            )
        except Exception as exc:
            raise SourceCreateStorageError(
                "Failed to create vector collection"
            ) from exc

        try:
            new_source = await self.source_crud.create_source(
                source_data=source_internal
            )
            logger.bind(
                source_uid=new_source.uid,
                source_type=new_source.source_type.value,
            ).info("Source created")
            return new_source
        except Exception as exc:
            # 回滚向量集合
            try:
                await asyncio.to_thread(
                    self.vector_db.delete_collection,
                    collection_name=source_internal.collection_name,
                )
            except Exception as rollback_exc:
                raise SourceCreateStorageError(
                    "Failed to create source and rollback vector collection"
                ) from rollback_exc

            # 抛出原始创建失败异常
            raise SourceCreateStorageError("Failed to create source") from exc

    async def update_source(
        self,
        *,
        source: Source,
        source_data: SourceUpdate,
    ) -> Source:
        """更新 Source 基础配置；更新 web_crawl_config 后重置状态。"""
        try:
            source_data = self._validate_and_normalize_source_update(
                source=source,
                source_data=source_data,
            )
        except SourceUpdateValidationError as exc:
            logger.bind(
                source_uid=source.uid,
                source_type=source.source_type.value,
            ).warning(
                "Source update rejected due to invalid configuration: {}", str(exc)
            )
            raise

        # 如果修改目标 source 为 WEB_CRAWL 类型，
        # 并且涉及到 web_crawl_config 修改，需要重设 source.status
        reset_status = (
            SourceProcessStatus.PENDING
            if (
                source.source_type == SourceType.WEB_CRAWL
                and "web_crawl_config" in source_data.model_fields_set
            )
            else None
        )

        if source_data.source_name is not None:
            # 确保 source 唯一
            existing_source = await self.source_crud.get_source_by_name(
                source_name=source_data.source_name
            )
            if existing_source and existing_source.id != source.id:
                logger.bind(source_uid=source.uid).warning(
                    "Source update rejected because the name already exists"
                )
                raise SourceUpdateConflictError(
                    "source with the same name already exists"
                )

        updated_source = await self.source_crud.update_source(
            source=source,
            source_data=source_data,
            reset_status=reset_status,
        )
        logger.bind(
            source_uid=updated_source.uid,
            status_reset=reset_status is not None,
        ).info("Source updated")
        return updated_source

    async def delete_source(self, *, source: Source) -> SourceDeleteResult:
        """删除 Source 及其下属数据库、向量集合和本地文件。"""
        # 获取 source 下所有的 storage_keys，用于删除本地文件
        storage_keys = list(
            dict.fromkeys(
                await self.source_crud.list_source_item_storage_keys_by_source_id(
                    source_id=source.id
                )
            )
        )
        source_item_count = await self.source_crud.count_source_items_by_source_id(
            source_id=source.id
        )

        # 删除向量集合
        vector_collection_deleted = await self._delete_vector_collection(
            collection_name=source.collection_name
        )

        deleted = await self.source_crud.delete_source_by_id(source_id=source.id)
        if not deleted:
            raise ValueError("Source not found")

        file_deleted_count = 0
        file_delete_failed_count = 0
        cleanup_errors: list[str] = []
        for storage_key in storage_keys:
            try:
                # TODO: 后续可以考虑优化，提高并发量
                # 删除本地文件
                file_deleted = await self.file_storage.delete_file(key=storage_key)
                if file_deleted:
                    file_deleted_count += 1
            except Exception as exc:
                file_delete_failed_count += 1
                cleanup_errors.append("failed to delete a source file")
                logger.bind(
                    event="source.file_cleanup.failed",
                    source_uid=source.uid,
                ).opt(exception=exc).warning("Source file cleanup failed")

        result = SourceDeleteResult(
            deleted_source_item_count=source_item_count,
            file_deleted_count=file_deleted_count,
            file_delete_failed_count=file_delete_failed_count,
            vector_collection_deleted=vector_collection_deleted,
            cleanup_errors=cleanup_errors,
        )
        logger.bind(
            source_uid=source.uid,
            deleted_source_item_count=result.deleted_source_item_count,
            file_delete_failed_count=result.file_delete_failed_count,
        ).info("Source deleted")
        return result

    async def _delete_vector_collection(self, *, collection_name: str) -> bool:
        """删除向量集合；集合已不存在时视为无需清理。"""
        try:
            await asyncio.to_thread(
                self.vector_db.delete_collection,
                collection_name=collection_name,
            )
            return True
        except Exception as exc:
            message = str(exc).lower()
            if "not found" in message or "does not exist" in message:
                logger.info("Source vector collection already missing during deletion")
                return False
            raise SourceDeleteStorageError(
                "Failed to delete vector collection"
            ) from exc

    def _validate_and_normalize_source_create(
        self, source_data: SourceCreate
    ) -> SourceCreate:
        """根据 source_type 验证和规范化 SourceCreate 数据。"""
        if source_data.source_type == SourceType.LOCAL_FILE:
            # LOCAL_FILE 类型不允许设置 web_crawl_config
            if source_data.web_crawl_config is not None:
                raise SourceCreateValidationError(
                    "local_file source does not accept web_crawl_config"
                )
            return source_data

        if source_data.source_type == SourceType.WEB_CRAWL:
            # WEB_CRAWL 类型必须设置 web_crawl_config
            if source_data.web_crawl_config is None:
                raise SourceCreateValidationError(
                    "web_crawl source requires web_crawl_config"
                )

            return source_data.model_copy(
                update={
                    "web_crawl_config": self._validate_and_normalize_web_crawl_config(
                        source_data.web_crawl_config,
                        error_cls=SourceCreateValidationError,
                    )
                }
            )

        # 暂不支持其它 source_type 类型
        raise SourceCreateValidationError(
            f"Unsupported source_type: {source_data.source_type}"
        )

    def _validate_and_normalize_source_update(
        self,
        *,
        source: Source,
        source_data: SourceUpdate,
    ) -> SourceUpdate:
        """根据已有 source 类型校验更新数据，避免修改 source_type 边界。"""
        if "web_crawl_config" not in source_data.model_fields_set:
            return source_data

        if source.source_type != SourceType.WEB_CRAWL:
            if source_data.web_crawl_config is not None:
                raise SourceUpdateValidationError(
                    "local_file source does not accept web_crawl_config"
                )
            return source_data

        if source_data.web_crawl_config is None:
            raise SourceUpdateValidationError(
                "web_crawl source requires web_crawl_config"
            )

        return source_data.model_copy(
            update={
                "web_crawl_config": self._validate_and_normalize_web_crawl_config(
                    source_data.web_crawl_config,
                    error_cls=SourceUpdateValidationError,
                )
            }
        )

    def _validate_and_normalize_web_crawl_config(
        self,
        config: WebCrawlConfig,
        *,
        error_cls: type[Exception],
    ) -> WebCrawlConfig:
        """验证并规范化 WebCrawlConfig 配置。"""
        if config.entry_type == CrawlEntryType.URL_LIST and not config.urls:
            raise error_cls("urls is required when entry_type is url_list")
        if config.entry_type == CrawlEntryType.SITEMAP_URL and not config.sitemap_url:
            raise error_cls("sitemap_url is required when entry_type is sitemap_url")
        if config.entry_type == CrawlEntryType.SITE_ROOT and not config.site_root_url:
            raise error_cls("site_root_url is required when entry_type is site_root")

        seed_urls: list[str] = []
        if config.urls:
            seed_urls.extend(str(url) for url in config.urls)
        if config.sitemap_url:
            seed_urls.append(str(config.sitemap_url))
        if config.site_root_url:
            seed_urls.append(str(config.site_root_url))

        # 补齐爬取范围，减少前端必须手写的配置项。
        allowed_domains = config.allowed_domains or sorted(
            {hostname_from_url(url) for url in seed_urls}
        )
        if not allowed_domains:
            raise error_cls("web_crawl_config must resolve at least one allowed domain")

        include_paths = config.include_paths
        if config.entry_type == CrawlEntryType.SITE_ROOT and not include_paths:
            include_paths = sorted({path_prefix_from_url(url) for url in seed_urls})

        return config.model_copy(
            update={
                "allowed_domains": allowed_domains,
                "include_paths": include_paths,
            }
        )
