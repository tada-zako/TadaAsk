from dataclasses import dataclass
from typing import Any, Mapping


from ..models import ParsedDocument


@dataclass
class WebPageMetadata:
    """web crawl 元信息数据结构定义"""

    etag: str | None = None
    last_modified: str | None = None
    last_fetch_status: int | None = None
    content_type: str | None = None
    matched_extraction_rule: str | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "WebPageMetadata":
        """从 dict 数据创建 WebPageMetadata 实例；忽略字典中多余的字段"""
        if not data:
            return cls()

        allowed = cls.__dataclass_fields__.keys()
        return cls(**{key: value for key, value in data.items() if key in allowed})


@dataclass
class DiscoveredURL:
    """发现的 URL 信息"""

    item_key: str
    discovered_url: str  # discovered_url；包括 normalized url, sitemap 提取的 url, 以及从 site root BFS 检索到的 url
    depth: int = 0


@dataclass
class FetchedPage:
    """已抓取页面信息"""

    item_key: str
    discovered_url: str
    final_url: str  # 最终抓取到的 url；例如经过重定向后的 url
    html: str | None

    # 抓取相关元信息
    status_code: int
    content_type: str | None
    etag: str | None
    last_modified: str | None
    not_modified: bool = False  # 标记页面是否未修改


@dataclass
class ParsedPage:
    """已解析页面信息"""

    item_key: str
    discovered_url: str
    final_url: str
    parsed_document: ParsedDocument

    parsed_markdown_hash: str
    fetch_metadata: WebPageMetadata


@dataclass
class PageExtractionOptions:
    """页面内容提取配置"""

    content_selectors: list[str]
    exclude_selectors: list[str]
    title_selector: str | None = None
    matched_rule_name: str | None = None
