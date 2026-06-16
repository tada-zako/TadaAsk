import pymupdf
import pymupdf4llm

from .base import ParsedDocument, title_from_filename
from app.core.exceptions import FileParserError


class PDFParser:
    """PDF 解析器骨架：输出 Markdown，并保留页边界用于后续 citation"""

    def parse(self, file_input: bytes, filename: str) -> ParsedDocument:
        try:
            with pymupdf.open(stream=file_input, filetype="pdf") as doc:
                # 解析结果按分页组织
                page_chunks = pymupdf4llm.to_markdown(doc, page_chunks=True)
        except Exception as exc:
            raise FileParserError(f"Failed to parse PDF file: {filename}") from exc

        text_parts: list[str] = []
        page_boundaries: list[tuple[int, int]] = []
        cursor = 0

        for page in page_chunks:
            # 类型兼容处理
            page_text = page.get("text", "") if isinstance(page, dict) else str(page)
            if not page_text.strip():
                continue

            if text_parts:
                text_parts.append("\n\n")
                cursor += 2

            start = cursor
            text_parts.append(page_text)
            cursor += len(page_text)
            page_boundaries.append((start, cursor))

        return ParsedDocument(
            text="".join(text_parts),
            title=title_from_filename(filename),
            source_type="pdf",
            page_boundaries=page_boundaries,
        )
