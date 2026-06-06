from .file_parser import FileParser, ParsedDocument
from .pdf_parser import PDFParser

__all__ = ["FileParser", "ParsedDocument", "PDFParser"]


class FileParserFactory:
    def generate(self, file_type: str) -> FileParser:
        # 假设有这么个接口
        ...
