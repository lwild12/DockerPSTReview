from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


class RenderError(Exception):
    pass


def render_office_document_to_pdf(content: bytes, filename: str, timeout: int = 120) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        src = tmp_path / (filename or "document")
        src.write_bytes(content)
        try:
            result = subprocess.run(
                [
                    "soffice",
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(tmp_path),
                    str(src),
                ],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except FileNotFoundError as exc:
            raise RenderError("soffice is not installed") from exc
        except subprocess.TimeoutExpired as exc:
            raise RenderError(f"soffice timed out after {timeout}s") from exc

        if result.returncode != 0:
            raise RenderError(f"soffice failed (exit {result.returncode}): {result.stderr.strip()}")

        pdf_path = src.with_suffix(".pdf")
        if not pdf_path.exists():
            raise RenderError("soffice did not produce a PDF output")
        return pdf_path.read_bytes()
