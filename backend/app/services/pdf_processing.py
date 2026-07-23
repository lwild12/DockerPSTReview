from __future__ import annotations

from dataclasses import dataclass

import fitz


@dataclass
class RedactionRect:
    page_number: int
    x: float
    y: float
    width: float
    height: float


def burn_in_redactions(doc: fitz.Document, redactions: list[RedactionRect]) -> None:
    """Permanently strip the content under each redaction rect — not an overlay.

    `page.add_redact_annot` + `page.apply_redactions()` removes the underlying
    text/image content within the rect; only afterwards do we fill it black,
    so there's nothing left to select/extract/copy out from under the box.
    """
    by_page: dict[int, list[RedactionRect]] = {}
    for r in redactions:
        by_page.setdefault(r.page_number, []).append(r)

    for page_number, page_redactions in by_page.items():
        if page_number < 0 or page_number >= doc.page_count:
            continue
        page = doc[page_number]
        for r in page_redactions:
            rect = fitz.Rect(r.x, r.y, r.x + r.width, r.y + r.height)
            page.add_redact_annot(rect, fill=(0, 0, 0))
        page.apply_redactions()


def stamp_bates(
    doc: fitz.Document, prefix: str, start_number: int, padding: int
) -> tuple[str, str, int]:
    """Stamp a sequential Bates number bottom-right on every page.

    Returns (first_label, last_label, next_start_number) so callers can chain
    numbering across multiple documents in one export.
    """
    counter = start_number
    first_label = ""
    last_label = ""
    for page in doc:
        label = f"{prefix}{str(counter).zfill(padding)}"
        if not first_label:
            first_label = label
        last_label = label
        rect = fitz.Rect(
            page.rect.width - 200,
            page.rect.height - 36,
            page.rect.width - 20,
            page.rect.height - 12,
        )
        page.insert_textbox(rect, label, fontsize=9, fontname="helv", align=fitz.TEXT_ALIGN_RIGHT)
        counter += 1
    return first_label, last_label, counter


def merge_documents(docs: list[fitz.Document]) -> fitz.Document:
    merged = fitz.open()
    for doc in docs:
        merged.insert_pdf(doc)
    return merged
