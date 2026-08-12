"""PDF-building engine for the Streamlit lab book builder."""

from __future__ import annotations

import io
import math
from dataclasses import dataclass
from typing import Sequence

from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas


TOC_MARKER = "__TOC__"
ENTRIES_PER_TOC_PAGE = 37


@dataclass(frozen=True)
class PdfDocument:
    """An uploaded PDF and the name shown in the table of contents."""

    document_id: str
    name: str
    data: bytes


def _reader(document: PdfDocument) -> PdfReader:
    reader = PdfReader(io.BytesIO(document.data))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as exc:  # pragma: no cover - depends on PDF encryption
            raise ValueError(f"{document.name} is password protected.") from exc
    return reader


def page_count(document: PdfDocument) -> int:
    """Return the number of pages in one uploaded document."""

    return len(_reader(document).pages)


def _toc_page_count(entry_count: int) -> int:
    return max(1, math.ceil(entry_count / ENTRIES_PER_TOC_PAGE))


def _shorten(c: canvas.Canvas, text: str, max_width: float) -> str:
    if c.stringWidth(text, "Helvetica", 10) <= max_width:
        return text
    shortened = text
    while shortened and c.stringWidth(shortened + "…", "Helvetica", 10) > max_width:
        shortened = shortened[:-1]
    return shortened + "…"


def _draw_toc_header(c: canvas.Canvas, title: str, page_number: int) -> float:
    width, height = letter
    left = 0.75 * inch
    right = 0.75 * inch
    top = height - 0.75 * inch

    heading = title if page_number == 1 else f"{title} (continued)"
    c.setFont("Helvetica-Bold", 18)
    c.drawString(left, top, heading)

    y = top - 0.5 * inch
    c.setFont("Helvetica-Bold", 11)
    c.drawString(left, y, "Document")
    c.drawRightString(width - right - 1.0 * inch, y, "Start Page")
    c.drawRightString(width - right, y, "Pages")
    y -= 0.2 * inch
    c.setLineWidth(1)
    c.line(left, y, width - right, y)
    return y - 0.25 * inch


def make_toc_pdf(entries: Sequence[tuple[str, int, int]], title: str) -> bytes:
    """Create a table of contents with as many pages as needed."""

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, _ = letter
    left = 0.75 * inch
    right = 0.75 * inch
    max_name_width = (width - left - right) - 2.4 * inch

    chunks = [entries[i : i + ENTRIES_PER_TOC_PAGE] for i in range(0, len(entries), ENTRIES_PER_TOC_PAGE)]
    if not chunks:
        chunks = [[]]

    for toc_page_number, chunk in enumerate(chunks, start=1):
        y = _draw_toc_header(c, title, toc_page_number)
        c.setFont("Helvetica", 10)
        for name, start_page, document_pages in chunk:
            c.drawString(left, y, _shorten(c, name, max_name_width))
            c.drawRightString(width - right - 1.0 * inch, y, str(start_page))
            c.drawRightString(width - right, y, str(document_pages))
            y -= 0.22 * inch

        c.setFont("Helvetica-Oblique", 9)
        c.drawString(left, 0.45 * inch, "Lab sheets combined into one document")
        c.showPage()

    c.save()
    return buffer.getvalue()


def _page_number_overlay(width: float, height: float, number: int) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(width, height))
    c.setFont("Helvetica", 10)
    c.drawCentredString(width / 2, 0.4 * inch, str(number))
    c.showPage()
    c.save()
    return buffer.getvalue()


def build_booklet(
    documents: Sequence[PdfDocument],
    ordered_items: Sequence[str],
    toc_title: str = "Table of Contents",
    include_toc: bool = True,
    add_page_numbers: bool = True,
) -> bytes:
    """Combine uploaded documents according to ordered_items and return PDF bytes."""

    document_by_id = {document.document_id: document for document in documents}
    ordered_ids = [item for item in ordered_items if item != TOC_MARKER]
    if not ordered_ids:
        raise ValueError("Upload and select at least one PDF.")
    if len(ordered_ids) != len(set(ordered_ids)):
        raise ValueError("The document order contains a duplicate entry.")
    if any(document_id not in document_by_id for document_id in ordered_ids):
        raise ValueError("The document list changed. Please upload the files again.")

    if include_toc:
        marker_index = ordered_items.index(TOC_MARKER) if TOC_MARKER in ordered_items else 0
        pre_ids = [item for item in ordered_items[:marker_index] if item != TOC_MARKER]
        post_ids = [item for item in ordered_items[marker_index + 1 :] if item != TOC_MARKER]
    else:
        pre_ids = ordered_ids
        post_ids = []

    counts = {document_id: page_count(document_by_id[document_id]) for document_id in ordered_ids}
    toc_pages = _toc_page_count(len(post_ids)) if include_toc else 0
    current_page = sum(counts[document_id] for document_id in pre_ids) + toc_pages + 1
    entries: list[tuple[str, int, int]] = []
    for document_id in post_ids:
        document = document_by_id[document_id]
        entries.append((document.name, current_page, counts[document_id]))
        current_page += counts[document_id]

    writer = PdfWriter()

    def append_document(document_id: str) -> None:
        for source_page in _reader(document_by_id[document_id]).pages:
            writer.add_page(source_page)

    for document_id in pre_ids:
        append_document(document_id)

    if include_toc:
        toc_reader = PdfReader(io.BytesIO(make_toc_pdf(entries, toc_title)))
        for toc_page in toc_reader.pages:
            writer.add_page(toc_page)

    for document_id in post_ids:
        append_document(document_id)

    if add_page_numbers:
        for index, output_page in enumerate(writer.pages, start=1):
            width = float(output_page.mediabox.width)
            height = float(output_page.mediabox.height)
            overlay = PdfReader(io.BytesIO(_page_number_overlay(width, height, index))).pages[0]
            output_page.merge_page(overlay)

    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()
