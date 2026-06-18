from dataclasses import dataclass


from ..models import ParsedDocument


@dataclass
class DiscoveredURL:
    """发现的 URL 信息"""

    item_key: str
    url: str
    depth: int = 0
    source_url: str | None = None


@dataclass
class FetchedPage:
    """已抓取页面信息"""

    item_key: str
    url: str
    final_url: str
    status_code: int
    html: str | None
    content_type: str | None
    etag: str | None
    last_modified: str | None
    raw_html_hash: str | None
    not_modified: bool = False


@dataclass
class ParsedPage:
    """已解析页面信息"""

    item_key: str
    origin_url: str
    final_url: str
    parsed_document: ParsedDocument
    raw_html_hash: str
    parsed_markdown_hash: str
    fetch_metadata: dict


@dataclass
class PageExtractionOptions:
    """页面内容提取配置"""

    content_selectors: list[str]
    exclude_selectors: list[str]
    title_selector: str | None = None
    matched_rule_name: str | None = None
