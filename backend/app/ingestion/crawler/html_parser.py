from bs4 import BeautifulSoup, Tag
from markdownify import MarkdownConverter

from . import FetchedPage, ParsedPage, PageExtractionOptions
from .. import ParsedDocument, ParsedSection
from app.utils import calculate_text_hash
from app.core.constants import SourceType


# 默认排除选择器；尽可能保持最简
DEFAULT_EXCLUDE_SELECTORS = [
    "script",
    "style",
    "noscript",
]
# 默认内容选择器列表
DEFAULT_CONTENT_SELECTORS = [
    "main",
    "article",
    "[role='main']",
    ".docs-content",
    ".documentation",
    ".markdown-body",
]


class HTMLPageParser:
    """
    HTML 页面解析器；
    负责清洗 fetched html 内容，并将 html 转换成 MD 文本输出
    """

    def parse(self, page: FetchedPage, *, options: PageExtractionOptions) -> ParsedPage:
        """解析 HTML 页面，提取文本内容并转换为 Markdown"""
        if page.not_modified:
            # 不解析未修改的页面
            raise ValueError("Cannot parse a not-modified page")
        if not page.html:
            raise ValueError(f"Fetched page {page.url} has no HTML content to parse")

        # 转换为 BeautifulSoup 对象进行解析
        soup = BeautifulSoup(page.html, "lxml")
        title = self._extract_title(soup, options=options)

        # 选择内容根节点，并清理噪音元素
        root = self._select_content_root(soup, options=options)
        self._remove_noise(root, options=options)

        # 转换为 MD 文本，提取 sections 并计算 hash
        markdown_text, sections = self._convert_to_markdown_with_sections(root)
        parsed_markdown_hash = calculate_text_hash(markdown_text)

        parsed_document = ParsedDocument(
            text=markdown_text,
            title=title,
            source_type=SourceType.WEB_CRAWL,
            sections=sections,
            metadata={
                "origin_url": page.url,
                "final_url": page.final_url,
                "content_type": page.content_type,
                "matched_extraction_rule": options.matched_rule_name,
            },
        )

        return ParsedPage(
            item_key=page.item_key,
            origin_url=page.url,
            final_url=page.final_url,
            parsed_document=parsed_document,
            raw_html_hash=page.raw_html_hash or "",
            parsed_markdown_hash=parsed_markdown_hash,
            fetch_metadata={
                "etag": page.etag,
                "last_modified": page.last_modified,
                "raw_html_hash": page.raw_html_hash,
                "parsed_markdown_hash": parsed_markdown_hash,
                "last_fetch_status": page.status_code,
                "final_url": page.final_url,
                "content_type": page.content_type,
                "matched_extraction_rule": options.matched_rule_name,
            },
        )

    def _extract_title(
        self, soup: BeautifulSoup, *, options: PageExtractionOptions
    ) -> str:
        """提取页面标题"""
        # 优先使用 options 中的 title_selector
        if options.title_selector:
            title_element = soup.select_one(options.title_selector)
            if title_element:
                title = title_element.get_text(" ", strip=True)
                if title:
                    return title

        if soup.title and soup.title.string:
            return soup.title.string.strip()

        # fallback: 尝试 <h1> 标签
        h1 = soup.find("h1")
        if h1 and h1.get_text():
            return h1.get_text(" ", strip=True)

        return "Untitled"

    def _select_content_root(
        self, soup: BeautifulSoup, *, options: PageExtractionOptions
    ) -> Tag:
        """选择内容根节点"""
        # 优先使用配置的内容选择器
        selectors = options.content_selectors or DEFAULT_CONTENT_SELECTORS
        for selector in selectors:
            root = soup.select_one(selector)
            if isinstance(root, Tag):
                return root

        # 如果没有找到，返回整个 body
        if not soup.body:
            raise ValueError("No <body> tag found in the HTML content")
        return soup.body

    def _remove_noise(self, root: Tag, *, options: PageExtractionOptions) -> None:
        """移除噪音元素"""
        exclude_selectors = options.exclude_selectors + DEFAULT_EXCLUDE_SELECTORS
        for selector in exclude_selectors:
            for element in root.select(selector):
                element.decompose()  # 从 DOM 中移除元素

    def _convert_to_markdown_with_sections(
        self, root: Tag
    ) -> tuple[str, list[ParsedSection]]:
        """
        将 HTML 转换为 Markdown，并提取 sections

        转换策略：
            - 通过遍历根结点的直接子节点，计算每个节点在 MD 中的位置
            - 将标题节点（h1-h6）作为 section 分割点，记录章节信息和跳转锚点
        """
        parts: list[str] = []  # 转换后的 Markdown 文本块
        sections: list[ParsedSection] = []  # 解析出的章节信息

        # 遍历根节点的直接子节点
        for node in root.children:
            if not isinstance(node, Tag):
                continue

            if node.name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
                # 处理标题节点，记录跳转锚点
                current_pos = sum(len(part) for part in parts)
                if sections and sections[-1].end is None:
                    sections[-1].end = current_pos

                header = node.get_text(" ", strip=True)
                anchor = f"#{node['id']}" if node.has_attr("id") else None

                sections.append(
                    ParsedSection(
                        start=current_pos,
                        end=None,
                        level=int(node.name[1]),
                        header=header,
                        anchor=anchor,
                    )
                )

            # 将节点转换为 Markdown
            rendered = MarkdownConverter(heading_style="ATX").convert_soup(node)
            if rendered:
                parts.append(rendered + "\n\n")

        markdown_text = "".join(parts).strip() + "\n"

        if sections and sections[-1].end is None:
            sections[-1].end = len(markdown_text)

        return markdown_text, sections
