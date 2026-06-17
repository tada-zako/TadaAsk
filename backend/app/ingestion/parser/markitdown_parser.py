from io import BytesIO
from pathlib import Path

from markitdown import MarkItDown, StreamInfo

from .base import ParsedDocument, title_from_filename
from app.core.exceptions import FileParserError


class MarkItDownParser:
    """MarkItDown 适配器：面向泛文档格式输出 Markdown"""

    def __init__(self):
        self._converter = MarkItDown(enable_plugins=False)

    def parse(self, file_input: bytes, filename: str) -> ParsedDocument:
        ext = Path(filename).suffix.lower()

        try:
            result = self._converter.convert_stream(
                BytesIO(file_input),
                stream_info=StreamInfo(extension=ext),
            )
        except Exception as exc:
            raise FileParserError(
                f"Failed to parse file with MarkItDown: {filename}"
            ) from exc

        return ParsedDocument(
            text=result.text_content,
            title=title_from_filename(filename),
            source_type=ext.lstrip(".") or "document",
        )
