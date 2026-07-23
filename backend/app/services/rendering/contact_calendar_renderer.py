from __future__ import annotations

from pathlib import Path

import weasyprint
from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html"]),
)


def render_contact_to_pdf(structured_metadata: dict) -> bytes:
    template = _env.get_template("contact_render.html")
    html_content = template.render(**structured_metadata)
    return weasyprint.HTML(string=html_content).write_pdf()


def render_calendar_to_pdf(subject: str, structured_metadata: dict) -> bytes:
    template = _env.get_template("calendar_render.html")
    context = {k: v for k, v in structured_metadata.items() if k != "subject"}
    html_content = template.render(subject=subject, **context)
    return weasyprint.HTML(string=html_content).write_pdf()


def render_unsupported_placeholder_to_pdf(
    filename: str, mime_type: str, size: int, content_hash: str
) -> bytes:
    template = _env.get_template("unsupported_placeholder.html")
    html_content = template.render(
        filename=filename, mime_type=mime_type, size=size, content_hash=content_hash
    )
    return weasyprint.HTML(string=html_content).write_pdf()
