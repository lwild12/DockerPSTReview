from __future__ import annotations

import io

import img2pdf
from PIL import Image


class RenderError(Exception):
    pass


def render_image_to_pdf(content: bytes) -> bytes:
    try:
        with Image.open(io.BytesIO(content)) as im:
            normalized = im.convert("RGB") if im.mode not in ("RGB", "L") else im
            buf = io.BytesIO()
            normalized.save(buf, format="PNG")
            png_bytes = buf.getvalue()
        return img2pdf.convert(png_bytes)
    except Exception as exc:
        raise RenderError(f"failed to render image to PDF: {exc}") from exc
