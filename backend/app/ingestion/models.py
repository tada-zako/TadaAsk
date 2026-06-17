from dataclasses import dataclass


@dataclass
class ParsedSection:
    """解析文档章节"""

    start: int
    header: str
    anchor: str | None = None  # 章节锚点；web 文档跳转定位
    end: int | None = None
    level: int | None = None


@dataclass
class ParsedDocument:
    """解析后的文档内容"""

    text: str  # 解析后的文档 MD 内容
    title: str  # 文档标题
    source_type: str
    lang_hint: str | None = None  # 代码文件的语言类型
    page_boundaries: list[tuple[int, int]] | None = (
        None  # 文档文本块的页码边界列表（仅适用于 PDF 等分页文档；page: (start, end)）
    )
    sections: list[ParsedSection] | None = None  # 文档章节列表
    metadata: dict | None = None  # 解析过程中提取的额外元信息
