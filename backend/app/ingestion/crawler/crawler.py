import asyncio
from fnmatch import fnmatch
from urllib.parse import urlparse

import httpx

from . import (
    PageExtractionOptions,
    DiscoveredURL,
    FetchedPage,
    WebPageMetadata,
)
from app.db.schemas import WebCrawlConfig, WebCrawlExtractionRule
from app.utils import normalize_url
from app.core.constants import CrawlEntryType


class WebCrawler:
    """负责 Web Crawl Config 的处理和解析，并进行网页爬取"""

    def __init__(
        self,
        *,
        timeout: float = 20.0,
        user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    ):
        self.timeout = timeout
        self.user_agent = user_agent

    async def discover_urls(self, config: WebCrawlConfig) -> list[DiscoveredURL]:
        """根据 WebCrawlConfig 进行 URL 发现，返回待爬取的 URL 列表"""
        if config.entry_type == CrawlEntryType.URL_LIST:
            return self._discover_url_list(config)

        if config.entry_type == CrawlEntryType.SITEMAP_URL:
            raise NotImplementedError("sitemap discovery is not implemented yet")

        if config.entry_type == CrawlEntryType.SITE_ROOT:
            raise NotImplementedError("site root discovery is not implemented yet")

        raise ValueError(f"Unsupported entry_type: {config.entry_type}")

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
            discovered.append(
                DiscoveredURL(item_key=item_key, discovered_url=url, depth=0)
            )
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

    def create_http_client(self) -> httpx.AsyncClient:
        """创建 HTTP 客户端实例"""
        return httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml",
            },
        )

    async def fetch_page(
        self,
        *,
        client: httpx.AsyncClient,
        discovered: DiscoveredURL,
        config: WebCrawlConfig,
        previous_metadata: WebPageMetadata | None,
    ) -> FetchedPage:
        """抓取页面内容，并返回 FetchedPage"""
        # 构建请求头，包含 If-None-Match 和 If-Modified-Since
        headers = {}
        if previous_metadata:
            if etag := previous_metadata.etag:
                headers["If-None-Match"] = etag
            if last_modified := previous_metadata.last_modified:
                headers["If-Modified-Since"] = last_modified

        # 爬取延迟
        if config.request_delay_ms:
            await asyncio.sleep(config.request_delay_ms / 1000.0)

        # 发起请求
        response = await client.get(discovered.discovered_url, headers=headers)

        if response.status_code == 304:
            # 页面未修改
            return FetchedPage(
                item_key=discovered.item_key,
                discovered_url=discovered.discovered_url,
                final_url=str(response.url),
                status_code=304,
                html=None,
                content_type=response.headers.get("content-type"),
                etag=response.headers.get("etag"),
                last_modified=response.headers.get("last-modified"),
                not_modified=True,
            )

        response.raise_for_status()
        html = response.text

        return FetchedPage(
            item_key=discovered.item_key,
            discovered_url=discovered.discovered_url,
            final_url=str(response.url),
            status_code=response.status_code,
            html=html,
            content_type=response.headers.get("content-type"),
            etag=response.headers.get("etag"),
            last_modified=response.headers.get("last-modified"),
            not_modified=False,
        )

    def resolve_extraction_options(
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
