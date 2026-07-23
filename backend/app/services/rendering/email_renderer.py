from __future__ import annotations

from datetime import datetime
from pathlib import Path

import nh3
import weasyprint
from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html"]),
)


def _block_network_fetcher(url: str):
    """Never let WeasyPrint fetch a network resource while rendering email HTML —
    otherwise a tracking pixel or crafted `<img>` tag becomes an SSRF vector /
    read-receipt leak triggered just by importing a PST."""
    if url.startswith("data:"):
        return weasyprint.default_url_fetcher(url)
    raise ValueError(f"blocked network fetch during PDF rendering: {url}")


def render_email_to_pdf(
    subject: str,
    sender: str,
    recipients_to: list[str],
    recipients_cc: list[str],
    sent_at: datetime | None,
    body_text: str,
    body_html: str,
) -> bytes:
    template = _env.get_template("email_render.html")
    safe_html = nh3.clean(body_html) if body_html else ""
    html_content = template.render(
        subject=subject,
        sender=sender,
        recipients_to=recipients_to,
        recipients_cc=recipients_cc,
        sent_at=sent_at.isoformat() if sent_at else "",
        body_text=body_text,
        body_html=safe_html,
    )
    return weasyprint.HTML(string=html_content, url_fetcher=_block_network_fetcher).write_pdf()
