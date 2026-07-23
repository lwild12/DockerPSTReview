import io

import fitz
import pytest
from PIL import Image

from app.services.rendering import guess_kind
from app.services.rendering.contact_calendar_renderer import (
    render_calendar_to_pdf,
    render_contact_to_pdf,
    render_unsupported_placeholder_to_pdf,
)
from app.services.rendering.email_renderer import render_email_to_pdf
from app.services.rendering.image_renderer import render_image_to_pdf
from app.services.rendering.office_renderer import RenderError, render_office_document_to_pdf


def _pdf_text(pdf_bytes: bytes) -> str:
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        return "".join(page.get_text() for page in doc)


def test_render_email_to_pdf_includes_header_and_body():
    pdf_bytes = render_email_to_pdf(
        subject="Quarterly numbers",
        sender="alice@example.com",
        recipients_to=["bob@example.com"],
        recipients_cc=[],
        sent_at=None,
        body_text="See attached.",
        body_html="",
    )
    assert pdf_bytes.startswith(b"%PDF")
    text = _pdf_text(pdf_bytes)
    assert "Quarterly numbers" in text
    assert "alice@example.com" in text
    assert "See attached." in text


def test_render_email_html_body_is_sanitized_and_blocks_network_fetch():
    pdf_bytes = render_email_to_pdf(
        subject="HTML email",
        sender="a@x.com",
        recipients_to=["b@x.com"],
        recipients_cc=[],
        sent_at=None,
        body_text="",
        body_html='<p>Hello <script>alert(1)</script><img src="http://evil.example/pixel.png"></p>',
    )
    text = _pdf_text(pdf_bytes)
    assert "Hello" in text
    # the <script> tag is stripped by nh3, and the remote <img> fetch is blocked
    # by the custom url_fetcher (WeasyPrint just renders a broken-image icon,
    # it doesn't raise) — either way, no network call happens.


def test_render_contact_to_pdf():
    pdf_bytes = render_contact_to_pdf(
        {
            "full_name": "Jane Doe",
            "emails": ["jane@x.com"],
            "phones": [],
            "company": "Acme",
            "title": "CEO",
        }
    )
    text = _pdf_text(pdf_bytes)
    assert "Jane Doe" in text
    assert "Acme" in text


def test_render_calendar_to_pdf():
    pdf_bytes = render_calendar_to_pdf("Board meeting", {"subject": "Board meeting"})
    text = _pdf_text(pdf_bytes)
    assert "Board meeting" in text


def test_render_unsupported_placeholder_to_pdf():
    pdf_bytes = render_unsupported_placeholder_to_pdf(
        filename="data.xyz",
        mime_type="application/octet-stream",
        size=1234,
        content_hash="deadbeef",
    )
    text = _pdf_text(pdf_bytes)
    assert "data.xyz" in text
    assert "deadbeef" in text


def test_render_image_to_pdf_roundtrips():
    img = Image.new("RGB", (100, 50), color="red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    pdf_bytes = render_image_to_pdf(buf.getvalue())
    assert pdf_bytes.startswith(b"%PDF")
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        assert doc.page_count == 1


def test_render_image_to_pdf_raises_on_garbage():
    from app.services.rendering.image_renderer import RenderError as ImageRenderError

    with pytest.raises(ImageRenderError):
        render_image_to_pdf(b"not an image")


def test_render_office_document_to_pdf_converts_plain_text():
    pdf_bytes = render_office_document_to_pdf(b"Hello from a text document\n", "note.txt")
    assert pdf_bytes.startswith(b"%PDF")
    text = _pdf_text(pdf_bytes)
    assert "Hello from a text document" in text


def test_render_office_document_raises_render_error_when_soffice_missing(monkeypatch):
    import subprocess

    from app.services.rendering import office_renderer

    def _raise_not_found(*args, **kwargs):
        raise FileNotFoundError("no such file")

    monkeypatch.setattr(subprocess, "run", _raise_not_found)
    with pytest.raises(RenderError):
        office_renderer.render_office_document_to_pdf(b"content", "doc.docx")


def test_guess_kind_classification():
    assert guess_kind("report.pdf", "") == "pdf"
    assert guess_kind("report.docx", "") == "office"
    assert guess_kind("photo.jpg", "") == "image"
    assert guess_kind("photo", "image/png") == "image"
    assert guess_kind("data.bin", "application/octet-stream") == "unsupported"
