from typing import Iterable
from pathlib import Path

from .base import FileParser, FileParserError, ParsedDocument
from .code_parser import CodeParser
from .markitdown_parser import MarkItDownParser
from .pdf_parser import PDFParser
from app.core.constants import (
    AST_CODE_EXTS,
    OTHER_CODE_EXTS,
    PDF_EXTS,
    DOC_EXTS,
    DATA_EXTS,
    TEXT_EXTS,
)

__all__ = [
    "CodeParser",
    "FileParser",
    "FileParserError",
    "MarkItDownParser",
    "PDFParser",
    "ParsedDocument",
    "FileParserFactory",
    "create_default_file_parser_factory",
]


class FileParserFactory:
    """基于文件扩展名的 FileParser 注册器工厂"""

    def __init__(self, registry: dict[str, FileParser] | None = None):
        self._registry: dict[str, FileParser] = {}

        if registry:
            for file_type, parser in registry.items():
                self.register(file_type, parser)

    @staticmethod
    def normalize_file_type(file_type: str) -> str:
        """标准化扩展名，允许传入 '.pdf'、'pdf' 或完整文件名"""
        normalized = file_type.strip().lower()
        if not normalized:
            raise ValueError("File type cannot be empty")

        if normalized.startswith("."):
            return normalized

        suffix = Path(normalized).suffix.lower()
        if suffix:
            return suffix

        return f".{normalized}"

    def register(
        self,
        file_type: str,
        file_parser: FileParser,
        *,
        overwrite: bool = False,
    ) -> "FileParserFactory":
        """注册单个扩展名到 parser 的映射"""
        normalized = self.normalize_file_type(file_type)
        if not overwrite and normalized in self._registry:
            raise ValueError(
                f"FileParser already registered for file type: {normalized}"
            )

        self._registry[normalized] = file_parser
        return self

    def register_many(
        self,
        file_types: Iterable[str],
        file_parser: FileParser,
        *,
        overwrite: bool = False,
    ) -> "FileParserFactory":
        """将多个扩展名注册到同一个 parser"""
        for file_type in file_types:
            self.register(file_type, file_parser, overwrite=overwrite)
        return self

    def generate(self, file_type: str) -> FileParser:
        """基于扩展名或文件名返回对应 parser"""
        normalized = self.normalize_file_type(file_type)
        if normalized not in self._registry:
            raise ValueError(f"No FileParser registered for file type: {normalized}")

        return self._registry[normalized]

    def supported_file_types(self) -> tuple[str, ...]:
        """返回已注册的扩展名列表"""
        return tuple(sorted(self._registry))


def create_default_file_parser_factory() -> FileParserFactory:
    """创建 OpenKapa 默认文件解析器注册表"""
    factory = FileParserFactory()

    markitdown_parser = MarkItDownParser()
    code_parser = CodeParser()
    pdf_parser = PDFParser()

    # PDF 文件注册
    factory.register_many(PDF_EXTS, pdf_parser)

    # 文档、数据、文本文件类型注册
    factory.register_many(
        DOC_EXTS,
        markitdown_parser,
    )
    factory.register_many(
        TEXT_EXTS,
        markitdown_parser,
    )
    factory.register_many(
        DATA_EXTS,
        markitdown_parser,
    )

    # 代码文件注册（区分 AST 和普通代码文件）
    factory.register_many(
        AST_CODE_EXTS,
        code_parser,
    )
    factory.register_many(
        OTHER_CODE_EXTS,
        code_parser,
    )

    return factory
