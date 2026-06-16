from pathlib import Path

from .base import ParsedDocument, decode_text_file, title_from_filename
from app.core.constants import EXTENSION_MAP


class CodeParser:
    """源码文件解析器：保留原始源码，交给 AST-aware splitter 处理"""

    def parse(self, file_input: bytes, filename: str) -> ParsedDocument:
        ext = Path(filename).suffix.lower()
        text = decode_text_file(file_input, filename)

        return ParsedDocument(
            text=text,
            title=title_from_filename(filename),
            source_type="code",
            lang_hint=EXTENSION_MAP.get(ext),
        )
