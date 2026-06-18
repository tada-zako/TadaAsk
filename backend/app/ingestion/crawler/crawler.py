import asyncio
from typing import AsyncIterable
from fnmatch import fnmatch
from urllib.parse import urlparse

import httpx

from . import (
    PageExtractionOptions,
    ParsedPage,
    DiscoveredURL,
    FetchedPage,
    HTMLPageParser,
)
from app.db.schemas import WebCrawlConfig, WebCrawlExtractionRule
from app.utils import (
    normalize_url,
    hostname_from_url,
    path_prefix_from_url,
    calculate_text_hash,
)
from app.core.constants import CrawlEntryType


class WebCrawler:
    """负责 Web Crawl Config 的处理和解析，并进行网页爬取"""

    def __init__(
        self,
        *,
        html_parser: HTMLPageParser,
        timeout: float = 20.0,
        # TODO: 后续自定义这里的 User Agent
        user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    ):
        self.html_parser = html_parser
        self.timeout = timeout
        self.user_agent = user_agent

    async def crawl(
        self,
        config: WebCrawlConfig,
        *,
        previous_metadata_by_item_key: dict[str, dict] | None = None,
    ) -> AsyncIterable[ParsedPage]:
        """根据 WebCrawlConfig 进行爬取，并产出 ParsedPage"""
        # 校验 config 的合法性
        config = self._validate_and_normalize_config(config)

        discovered_urls = self._discover_urls(config)

        semaphore = asyncio.Semaphore(config.concurrency)  # 限制并发数，避免过度爬取

        # 开启异步 client
        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml",
            },
        ) as client:
            # 单个 worker 流程
            async def worker(discovered: DiscoveredURL) -> ParsedPage | None:
                async with semaphore:
                    # 获取之前爬取的元数据
                    previous_metadata = (previous_metadata_by_item_key or {}).get(
                        discovered.item_key
                    )

                    page: FetchedPage = await self._fetch_page(
                        client=client,
                        discovered=discovered,
                        config=config,
                        previous_metadata=previous_metadata,
                    )

                    if page.not_modified:
                        return None  # 页面未修改，无需重新解析

                    # 处理页面解析配置
                    options = self._resolve_extraction_options(
                        config=config, url=page.final_url
                    )
                    return self.html_parser.parse(page=page, options=options)

            # 创建 worker 任务
            tasks = [
                asyncio.create_task(worker(discovered))
                for discovered in discovered_urls
            ]

            # 逐个获取结果
            for task in asyncio.as_completed(tasks):
                parsed_page = await task
                if parsed_page:
                    yield parsed_page

    def _validate_and_normalize_config(self, config: WebCrawlConfig) -> WebCrawlConfig:
        """校验 WebCrawlConfig 的合法性，并对 Config 进行规范化"""
        if config.entry_type == CrawlEntryType.URL_LIST and not config.urls:
            raise ValueError("urls is required when entry_type is url_list")
        if config.entry_type == CrawlEntryType.SITEMAP_URL and not config.sitemap_url:
            raise ValueError("sitemap_url is required when entry_type is sitemap_url")
        if config.entry_type not in {
            CrawlEntryType.URL_LIST,
            CrawlEntryType.SITEMAP_URL,
        }:
            raise ValueError(f"Unsupported entry_type: {config.entry_type}")

        # 确保 config 配置字段的全面
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

        # 推断 include_paths 配置
        include_paths = config.include_paths
        if config.entry_type == CrawlEntryType.SITE_ROOT and not include_paths:
            include_paths = sorted(
                {path_prefix_from_url(url) for url in seed_urls}
            )  # 默认使用 site_root_url 的路径前缀作为 include_paths

        return config.model_copy(
            update={
                "allowed_domains": allowed_domains,
                "include_paths": include_paths,
            }
        )

    def _discover_urls(self, config: WebCrawlConfig) -> list[DiscoveredURL]:
        """根据 WebCrawlConfig 进行 URL 发现，返回待爬取的 URL 列表"""
        if config.entry_type == CrawlEntryType.URL_LIST:
            return self._discover_url_list(config)

        raise NotImplementedError(
            f"Entry type {config.entry_type} is not supported yet"
        )

    def _discover_url_list(self, config: WebCrawlConfig) -> list[DiscoveredURL]:
        """从 URL 列表中进行 URL 发现"""
        discovered: list[DiscoveredURL] = []
        seen: set[str] = set()

        for raw_url in config.urls or []:
            # 提取 item_key
            url = normalize_url(str(raw_url))
            item_key = url

            if item_key in seen:
                continue
            if not self._is_allowed_url(url, config=config, depth=0):
                continue

            seen.add(item_key)
            discovered.append(DiscoveredURL(item_key=item_key, url=url))
            # 限制最大爬取页面数
            if len(discovered) >= config.max_pages:
                break

        return discovered

    def _is_allowed_url(self, url: str, *, config: WebCrawlConfig, depth: int) -> bool:
        """判断 URL 是否允许爬取"""
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return False
        if parsed.hostname not in set(config.allowed_domains):
            return False
        if depth > config.max_depth:
            return False

        path = parsed.path or "/"
        if config.include_paths and not any(
            path.startswith(prefix) for prefix in config.include_paths
        ):
            return False
        if config.exclude_paths and any(
            path.startswith(prefix) for prefix in config.exclude_paths
        ):
            return False
        return True

    async def _fetch_page(
        self,
        *,
        client: httpx.AsyncClient,
        discovered: DiscoveredURL,
        config: WebCrawlConfig,
        previous_metadata: dict | None,
    ) -> FetchedPage:
        """抓取页面内容，并返回 FetchedPage"""
        # 构建请求头，包含 If-None-Match 和 If-Modified-Since
        headers = {}
        if previous_metadata:
            if etag := previous_metadata.get("etag"):
                headers["If-None-Match"] = etag
            if last_modified := previous_metadata.get("last_modified"):
                headers["If-Modified-Since"] = last_modified

        # 爬取延迟
        if config.request_delay_ms:
            await asyncio.sleep(config.request_delay_ms / 1000.0)

        # 发起请求
        response = await client.get(discovered.url, headers=headers)

        if response.status_code == 304:
            # 页面未修改
            return FetchedPage(
                item_key=discovered.item_key,
                url=discovered.url,
                final_url=str(response.url),
                status_code=304,
                html=None,
                content_type=response.headers.get("content-type"),
                etag=response.headers.get("etag"),
                last_modified=response.headers.get("last-modified"),
                raw_html_hash=None,
                not_modified=True,
            )

        response.raise_for_status()
        html = response.text

        return FetchedPage(
            item_key=discovered.item_key,
            url=discovered.url,
            final_url=str(response.url),
            status_code=response.status_code,
            html=html,
            content_type=response.headers.get("content-type"),
            etag=response.headers.get("etag"),
            last_modified=response.headers.get("last-modified"),
            raw_html_hash=calculate_text_hash(html),
            not_modified=False,
        )

    def _resolve_extraction_options(
        self, *, config: WebCrawlConfig, url: str
    ) -> PageExtractionOptions:
        """根据 URL 和 WebCrawlConfig 解析页面内容提取配置"""
        # 全局匹配规则
        global_content_selectors = config.content_selectors
        global_exclude_selectors = config.exclude_selectors

        # 尝试匹配 URL 特定提取规则
        for rule in config.extraction_rules:
            if not self._matches_extraction_rule(discovered_url=url, rule=rule):
                continue

            content_selectors = rule.content_selectors or global_content_selectors
            exclude_selectors = rule.exclude_selectors + global_exclude_selectors

            return PageExtractionOptions(
                content_selectors=content_selectors,
                exclude_selectors=exclude_selectors,
                title_selector=rule.title_selector,
                matched_rule_name=rule.name,
            )

        # 如果没有匹配到特定规则，则使用全局配置
        return PageExtractionOptions(
            content_selectors=global_content_selectors,
            exclude_selectors=global_exclude_selectors,
            title_selector=None,
            matched_rule_name=None,
        )

    def _matches_extraction_rule(
        self, *, discovered_url: str, rule: WebCrawlExtractionRule
    ) -> bool:
        """判断 URL 是否匹配提取规则"""
        parsed = urlparse(discovered_url)
        path = parsed.path or "/"

        # URL 匹配
        exact_urls = {
            normalize_url(str(exact_url)) for exact_url in rule.url_match.exact_urls
        }
        if discovered_url in exact_urls:
            return True
        # 带有通配符的 URL 匹配
        if any(
            fnmatch(discovered_url, pattern) for pattern in rule.url_match.url_patterns
        ):
            return True

        # 路径前缀匹配
        if any(path.startswith(prefix) for prefix in rule.url_match.path_prefixes):
            return True
        # 路径通配符匹配
        if any(fnmatch(path, pattern) for pattern in rule.url_match.path_patterns):
            return True

        return False
