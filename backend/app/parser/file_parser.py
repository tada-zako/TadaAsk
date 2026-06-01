from typing import Protocol, runtime_checkable
from dataclasses import dataclass


from langchain_core.documents import Document


@dataclass
class ParsedDocument:
    """解析后的文档内容"""

    text: str  # 文档文本内容
    title: str  # 文档标题
    source_type: str
    lang_hint: str | None = None  # 代码文件的语言类型
    page_boundaries: list[tuple[int, int]] | None = (
        None  # 文档文本块的页码边界列表（仅适用于 PDF 等分页文档）
    )


@runtime_checkable
class FileParser(Protocol):
    """
    文件解析器协议：便于后期横向扩展不同类型的文件解析器（如 PDF、Word、文本等）
    """

    @staticmethod
    async def httpx_download(url: str) -> bytes:
        """
        httpx 方式请求下载文件内容
        """
        ...

    @staticmethod
    def parse(file_input: bytes, filename: str) -> ParsedDocument:
        """
        解析文件内容为文本块列表，每个文本块包含 page_content 和 metadata

        Args:
            file_input: 文件内容
            filename: 文件名，网络爬取的文件传入 url 的最后一部分

        Returns:
            文本块列表，每个文本块包含 page_content 和 metadata
        """
        ...
