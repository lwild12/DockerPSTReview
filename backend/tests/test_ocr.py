import io

import fitz
from PIL import Image, ImageDraw, ImageFont

from app.services import ocr
from app.services.rendering.image_renderer import render_image_to_pdf

_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _scanned_pdf(text: str) -> fitz.Document:
    img = Image.new("RGB", (900, 250), color="white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(_FONT_PATH, 40)
    draw.text((30, 90), text, fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    pdf_bytes = render_image_to_pdf(buf.getvalue())
    return fitz.open(stream=pdf_bytes, filetype="pdf")


def _text_pdf(text: str) -> fitz.Document:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    return doc


def test_has_extractable_text_false_for_scanned_image():
    with _scanned_pdf("CONFIDENTIAL INVOICE 998877") as doc:
        assert ocr.has_extractable_text(doc) is False


def test_has_extractable_text_true_for_real_text_pdf():
    with _text_pdf("This PDF already has a real text layer.") as doc:
        assert ocr.has_extractable_text(doc) is True


def test_ocr_pdf_extracts_text_from_scanned_image():
    with _scanned_pdf("CONFIDENTIAL INVOICE 998877") as doc:
        text = ocr.ocr_pdf(doc)
    assert "CONFIDENTIAL" in text
    assert "998877" in text


def test_ocr_pdf_handles_multiple_pages():
    doc = fitz.open()
    for label in ("PAGE ONE TEXT", "PAGE TWO TEXT"):
        page_doc = _scanned_pdf(label)
        doc.insert_pdf(page_doc)
        page_doc.close()

    text = ocr.ocr_pdf(doc)
    doc.close()
    assert "PAGE ONE" in text
    assert "PAGE TWO" in text
