from .file_parser import FileParser, ParsedDocument
from .pdf_parser import PDFParser

__all__ = ["FileParser", "ParsedDocument", "PDFParser"]


def file_parser_factory(file_type: str) -> FileParser:
    """文件解析器工厂：根据传入的文件类型返回对应的解析器实例"""
    if file_type == "pdf":
        return PDFParser()
    else:
        raise ValueError(f"Unsupported file type for parsing: {file_type}")
