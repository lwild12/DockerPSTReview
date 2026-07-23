OFFICE_EXTENSIONS = {".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt", ".rtf", ".odt"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp"}


class UnrenderableError(Exception):
    pass


def guess_kind(filename: str, mime_type: str) -> str:
    """Classify a native attachment file for rendering dispatch: pdf/office/image/unsupported."""
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if filename and "." in filename else ""
    mime_type = mime_type or ""
    if ext == ".pdf" or mime_type == "application/pdf":
        return "pdf"
    if ext in OFFICE_EXTENSIONS:
        return "office"
    if ext in IMAGE_EXTENSIONS or mime_type.startswith("image/"):
        return "image"
    return "unsupported"
