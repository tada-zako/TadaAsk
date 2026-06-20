import asyncio

from loguru import logger

from app.rag import VectorDatabase
from app.db.models import Source
from app.db.schemas import SourceCreate, SourceInternal, WebCrawlConfig
from app.crud import SourceCRUD
from app.utils import hostname_from_url, path_prefix_from_url
from app.core.constants import CrawlEntryType, SourceType
from app.core.exceptions import (
    SourceCreateConflictError,
    SourceCreateStorageError,
    SourceCreateValidationError,
)


class SourceCreationService:
    def __init__(
        self,
        *,
        source_crud: SourceCRUD,
        vector_db: VectorDatabase,
    ):
        self.source_crud = source_crud
        self.vector_db = vector_db

    async def create_source(self, source_data: SourceCreate) -> Source:
        """创建数据源的核心逻辑"""
        source_data = self._validate_and_normalize_source(source_data)

        # 检查同名数据源是否已存在
        existing_source = await self.source_crud.get_source_by_name(
            source_name=source_data.source_name
        )
        if existing_source:
            logger.warning(
                f"数据源名称 '{source_data.source_name}' 已存在，无法创建重复名称的数据源"
            )
            raise SourceCreateConflictError("source with the same name already exists")

        # 生成系统内部使用的数据源模型
        source_internal = SourceInternal(**source_data.model_dump())

        # 创建向量集合
        try:
            await asyncio.to_thread(
                self.vector_db.create_collection,
                collection_name=source_internal.collection_name,
            )
        except Exception as exc:
            logger.error(f"创建向量集合失败：{exc}")
            raise SourceCreateStorageError(
                "Failed to create vector collection"
            ) from exc
        # 创建数据库记录
        try:
            new_source = await self.source_crud.create_source(
                source_data=source_internal
            )
            logger.info(
                f"数据源 '{source_data.source_name}' 创建成功，UID：{new_source.uid}"
            )
            return new_source
        except Exception as exc:
            # 回滚向量集合
            logger.error(f"创建数据源记录失败：{exc}，正在回滚向量集合...")
            try:
                await asyncio.to_thread(
                    self.vector_db.delete_collection,
                    collection_name=source_internal.collection_name,
                )
                logger.info(f"已回滚向量集合 '{source_internal.collection_name}'")
            except Exception as rollback_exc:
                logger.error(f"回滚向量集合失败：{rollback_exc}")
                raise SourceCreateStorageError(
                    "Failed to create source and rollback vector collection"
                ) from rollback_exc

            # 抛出原始创建失败异常
            raise SourceCreateStorageError("Failed to create source") from exc

    def _validate_and_normalize_source(self, source_data: SourceCreate) -> SourceCreate:
        """根据 source_type 验证和规范化 SourceCreate 数据"""
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
                        source_data.web_crawl_config
                    )
                }
            )

        # 暂不支持其它 source_type 类型
        raise SourceCreateValidationError(
            f"Unsupported source_type: {source_data.source_type}"
        )

    def _validate_and_normalize_web_crawl_config(
        self, config: WebCrawlConfig
    ) -> WebCrawlConfig:
        """验证并规范化 WebCrawlConfig 配置"""
        if config.entry_type == CrawlEntryType.URL_LIST and not config.urls:
            raise SourceCreateValidationError(
                "urls is required when entry_type is url_list"
            )
        if config.entry_type == CrawlEntryType.SITEMAP_URL and not config.sitemap_url:
            raise SourceCreateValidationError(
                "sitemap_url is required when entry_type is sitemap_url"
            )
        if config.entry_type == CrawlEntryType.SITE_ROOT and not config.site_root_url:
            raise SourceCreateValidationError(
                "site_root_url is required when entry_type is site_root"
            )

        # 避免 config 配置字段缺失
        seed_urls: list[str] = []
        if config.urls:
            seed_urls.extend(str(url) for url in config.urls)
        if config.sitemap_url:
            seed_urls.append(str(config.sitemap_url))
        if config.site_root_url:
            seed_urls.append(str(config.site_root_url))

        # 推断 allowed_domains 配置
        allowed_domains = config.allowed_domains or sorted(
            {hostname_from_url(url) for url in seed_urls}
        )
        if not allowed_domains:
            raise SourceCreateValidationError(
                "web_crawl_config must resolve at least one allowed domain"
            )

        # 推断 include_paths 配置
        include_paths = config.include_paths
        if config.entry_type == CrawlEntryType.SITE_ROOT and not include_paths:
            include_paths = sorted({path_prefix_from_url(url) for url in seed_urls})

        return config.model_copy(
            update={
                "allowed_domains": allowed_domains,
                "include_paths": include_paths,
            }
        )
