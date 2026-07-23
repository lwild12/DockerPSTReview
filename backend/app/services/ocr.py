import fitz
import pytesseract
from PIL import Image

# Below this many extracted characters, a rendered PDF is treated as
# image-only (scanned) rather than as a document with a thin text layer.
MIN_EXTRACTABLE_CHARS = 20


class OcrError(Exception):
    pass


def has_extractable_text(doc: fitz.Document) -> bool:
    total_chars = sum(len(page.get_text().strip()) for page in doc)
    return total_chars >= MIN_EXTRACTABLE_CHARS


def ocr_pdf(doc: fitz.Document, dpi: int = 200) -> str:
    """Rasterize each page and run Tesseract over it. Runs synchronously —
    callers should offload this to a thread, since Tesseract is a blocking call."""
    try:
        page_texts = []
        for page in doc:
            pixmap = page.get_pixmap(dpi=dpi)
            image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
            page_texts.append(pytesseract.image_to_string(image))
        return "\n".join(page_texts).strip()
    except Exception as exc:
        raise OcrError(str(exc)) from exc
