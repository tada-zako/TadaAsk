import hashlib
import html
from dataclasses import dataclass
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas

from .models import BenchmarkDocument, BenchmarkLanguage, DocumentFormat


DOCUMENT_FORMAT_RATIO = {"markdown": 0.70, "pdf": 0.15, "html": 0.15}


@dataclass(slots=True)
class BuildDocument:
    id: str
    dataset: str
    title: str
    language: BenchmarkLanguage
    text: str
    is_distractor: bool = False


# TODO: _stable_key 函数重复次数较多，后续可以提取到 utils.py 模块中
def _stable_key(value: str) -> str:
    return hashlib.sha256(f"tadaask-rag-format:{value}".encode()).hexdigest()


def _wrap_pdf_lines(
    paragraph: str, font_name: str, font_size: int, max_width: float
) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in paragraph.split():
        candidate = f"{current} {word}".strip()
        if stringWidth(candidate, font_name, font_size) <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
            current = ""

        # Split unusually long paths or identifiers without dropping any characters.
        chunk = ""
        for character in word:
            if stringWidth(chunk + character, font_name, font_size) <= max_width:
                chunk += character
            else:
                if chunk:
                    lines.append(chunk)
                chunk = character
        current = chunk
    if current:
        lines.append(current)
    return lines or [""]


def _write_pdf(path: Path, title: str, text: str) -> None:
    """Render an ASCII document with the built-in PDF fonts."""
    canvas = Canvas(str(path), pagesize=A4, pageCompression=1)
    width, height = A4
    margin = 56
    y = height - margin

    for paragraph_index, paragraph in enumerate((title, *text.splitlines())):
        font_name = "Helvetica-Bold" if paragraph_index == 0 else "Helvetica"
        font_size = 15 if paragraph_index == 0 else 10
        canvas.setFont(font_name, font_size)
        if not paragraph.strip():
            y -= font_size
            continue
        for line in _wrap_pdf_lines(
            paragraph, font_name, font_size, width - margin * 2
        ):
            if y < margin:
                canvas.showPage()
                canvas.setFont(font_name, font_size)
                y = height - margin
            canvas.drawString(margin, y, line)
            y -= font_size * 1.45
        y -= font_size * 0.5
    canvas.save()


def render_corpus(
    documents: list[BuildDocument], output_dir: Path
) -> list[BenchmarkDocument]:
    """Render source documents and return their bundle-relative manifests.

    Args:
        documents: Selected documents with source text.
        output_dir: Root of the generated benchmark bundle.

    Returns:
        Metadata for every rendered corpus file.
    """
    corpus_dir = output_dir / "corpus"
    corpus_dir.mkdir(parents=True, exist_ok=True)
    pdf_target = round(len(documents) * DOCUMENT_FORMAT_RATIO["pdf"])
    html_target = round(len(documents) * DOCUMENT_FORMAT_RATIO["html"])

    # Standard PDF fonts cannot render CJK consistently across machines. Assign
    # PDF only to ASCII English documents and preserve validation text as a sidecar.
    pdf_ids = {
        item.id
        for item in sorted(
            (
                item
                for item in documents
                if item.language == BenchmarkLanguage.EN and item.text.isascii()
            ),
            key=lambda item: _stable_key(item.id),
        )[:pdf_target]
    }
    if len(pdf_ids) != pdf_target:
        raise ValueError("not enough English ASCII documents for the PDF target")
    html_ids = {
        item.id
        for item in sorted(
            (item for item in documents if item.id not in pdf_ids),
            key=lambda item: _stable_key(item.id),
        )[:html_target]
    }

    manifest: list[BenchmarkDocument] = []
    for item in sorted(documents, key=lambda document: document.id):
        filename_stem = item.id.replace(".", "-")
        validation_path: str | None = None

        if item.id in pdf_ids:
            document_format = DocumentFormat.PDF
            path = corpus_dir / f"{filename_stem}.pdf"
            _write_pdf(path, item.title, item.text)
            validation_file = corpus_dir / f"{filename_stem}.txt"
            validation_file.write_text(
                f"{item.title}\n\n{item.text}\n", encoding="utf-8"
            )
            validation_path = validation_file.relative_to(output_dir).as_posix()

        elif item.id in html_ids:
            document_format = DocumentFormat.HTML
            path = corpus_dir / f"{filename_stem}.html"
            paragraphs = "\n".join(
                f"<p>{html.escape(part)}</p>"
                for part in item.text.splitlines()
                if part.strip()
            )
            path.write_text(
                "<!doctype html>\n"
                '<html lang="en"><meta charset="utf-8">'
                f"<title>{html.escape(item.title)}</title>"
                f"<article><h1>{html.escape(item.title)}</h1>{paragraphs}</article>"
                "</html>\n",
                encoding="utf-8",
            )
            validation_file = corpus_dir / f"{filename_stem}.txt"
            validation_file.write_text(
                f"{item.title}\n\n{item.text}\n", encoding="utf-8"
            )
            validation_path = validation_file.relative_to(output_dir).as_posix()

        else:
            document_format = DocumentFormat.MARKDOWN
            path = corpus_dir / f"{filename_stem}.md"
            path.write_text(f"# {item.title}\n\n{item.text}\n", encoding="utf-8")

        manifest.append(
            BenchmarkDocument(
                id=item.id,
                dataset=item.dataset,
                title=item.title,
                language=item.language,
                document_format=document_format,
                relative_path=path.relative_to(output_dir).as_posix(),
                validation_text_path=validation_path,
                is_distractor=item.is_distractor,
            )
        )
    return manifest
