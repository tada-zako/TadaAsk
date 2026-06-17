from pathlib import Path
from typing import Protocol, runtime_checkable

from ..models import ParsedDocument
from app.core.exceptions import FileParserError


@runtime_checkable
class FileParser(Protocol):
    """
    文件解析器协议
    """

    def parse(self, file_input: bytes, filename: str) -> ParsedDocument:
        """
        解析文件

        Args:
            file_input: 文件内容
            filename: 文件名

        Returns:
            解析后的文档内容；返回类型为 ParsedDocument
        """
        ...


def decode_text_file(file_input: bytes, filename: str) -> str:
    """
    将文本类文件解码为标准换行的字符串；
    处理文件开头的 BOM
    """
    try:
        text = file_input.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise FileParserError(f"Unable to decode text file: {filename}") from exc

    return text.replace("\r\n", "\n").replace("\r", "\n")


def title_from_filename(filename: str) -> str:
    """从文件名中提取默认标题"""
    return Path(filename).stem or filename
