from __future__ import annotations

import io

import img2pdf
from PIL import Image


class RenderError(Exception):
    pass


# Without an explicit layout, img2pdf sizes the PDF page to the image's own
# pixel dimensions -- every image attachment ends up on its own oddly-sized
# page instead of the A4 every other rendered document (email, Office
# conversion) uses in this deployment. FitMode.into scales the image down
# to fit within the page without cropping or distorting it (letterboxed,
# not stretched); auto_orient flips to A4 landscape for wide images (a
# typical screenshot) instead of shrinking them tiny on a portrait page.
# A 10mm margin keeps the image off the page edges -- fit-into alone still
# lets one dimension run edge-to-edge, which reads as cropped/oversized
# next to every other rendered document type (all of which have padding).
_A4_PAGESIZE_PT = (img2pdf.mm_to_pt(210), img2pdf.mm_to_pt(297))
_A4_MARGIN_PT = img2pdf.mm_to_pt(10)
_A4_LAYOUT = img2pdf.get_layout_fun(
    pagesize=_A4_PAGESIZE_PT,
    border=(_A4_MARGIN_PT, _A4_MARGIN_PT),
    fit=img2pdf.FitMode.into,
    auto_orient=True,
)


def render_image_to_pdf(content: bytes) -> bytes:
    try:
        with Image.open(io.BytesIO(content)) as im:
            normalized = im.convert("RGB") if im.mode not in ("RGB", "L") else im
            buf = io.BytesIO()
            normalized.save(buf, format="PNG")
            png_bytes = buf.getvalue()
        return img2pdf.convert(png_bytes, layout_fun=_A4_LAYOUT)
    except Exception as exc:
        raise RenderError(f"failed to render image to PDF: {exc}") from exc
