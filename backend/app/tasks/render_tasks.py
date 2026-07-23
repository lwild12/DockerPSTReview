from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path

import fitz
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.celery_app import celery_app
from app.config import get_settings
from app.models.document import DedupStatus, DocType, Document, OcrStatus
from app.services import ocr, storage
from app.services.rendering import (
    UnrenderableError,
    email_renderer,
    guess_kind,
    image_renderer,
    office_renderer,
)
from app.services.rendering import contact_calendar_renderer as cc_renderer

logger = logging.getLogger(__name__)
settings = get_settings()


def _render_attachment_bytes(document: Document) -> bytes:
    content = Path(document.native_file_path).read_bytes()
    kind = guess_kind(document.subject, document.mime_type)

    if kind == "pdf":
        try:
            with fitz.open(stream=content, filetype="pdf") as doc:
                return doc.tobytes()
        except Exception as exc:
            raise UnrenderableError(f"invalid/corrupt PDF: {exc}") from exc
    if kind == "office":
        return office_renderer.render_office_document_to_pdf(content, document.subject)
    if kind == "image":
        return image_renderer.render_image_to_pdf(content)

    return cc_renderer.render_unsupported_placeholder_to_pdf(
        filename=document.subject,
        mime_type=document.mime_type,
        size=document.file_size,
        content_hash=document.content_hash,
    )


def render_document_bytes(document: Document) -> bytes:
    """Dispatch by doc_type/mime. Runs synchronously — callers should offload
    this to a thread, since WeasyPrint/soffice/Pillow are all blocking calls."""
    if document.doc_type == DocType.email:
        return email_renderer.render_email_to_pdf(
            subject=document.subject,
            sender=document.sender,
            recipients_to=document.recipients_to,
            recipients_cc=document.recipients_cc,
            sent_at=document.sent_at,
            body_text=document.body_text,
            body_html=document.body_html,
        )
    if document.doc_type == DocType.contact:
        return cc_renderer.render_contact_to_pdf(document.structured_metadata)
    if document.doc_type == DocType.calendar:
        return cc_renderer.render_calendar_to_pdf(document.subject, document.structured_metadata)
    if document.doc_type == DocType.attachment:
        return _render_attachment_bytes(document)
    raise ValueError(f"Unknown doc_type {document.doc_type}")


async def render_document(document_id: uuid.UUID, db: AsyncSession) -> None:
    document = await db.get(Document, document_id)
    if document is None:
        return

    try:
        pdf_bytes = await asyncio.to_thread(render_document_bytes, document)
    except Exception as exc:
        logger.warning(
            "Failed to render document %s, leaving unrendered", document_id, exc_info=True
        )
        document.render_error = str(exc)[:2000]
        await db.commit()
        return

    output_path = storage.rendered_dir(document.case_id) / f"{document.id}.pdf"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(pdf_bytes)

    page_count = 0
    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as opened:
            page_count = opened.page_count
            if document.doc_type == DocType.attachment and not ocr.has_extractable_text(opened):
                try:
                    document.ocr_text = await asyncio.to_thread(ocr.ocr_pdf, opened)
                    document.ocr_status = OcrStatus.completed
                    document.ocr_error = ""
                except ocr.OcrError as exc:
                    document.ocr_status = OcrStatus.failed
                    document.ocr_error = str(exc)[:2000]
                    logger.warning("OCR failed for document %s", document_id, exc_info=True)
    except Exception:
        logger.warning("Rendered PDF for %s failed to re-open for page count", document_id)

    document.rendered_pdf_path = str(output_path)
    document.rendered_pdf_page_count = page_count
    document.render_error = ""
    await db.commit()


async def render_documents_for_job(import_job_id: uuid.UUID, db: AsyncSession) -> None:
    """Render every primary (non-duplicate) document from one import job.
    Duplicates reuse their primary's rendered PDF at export time instead."""
    result = await db.execute(
        select(Document.id).where(
            Document.import_job_id == import_job_id,
            Document.dedup_status == DedupStatus.primary,
        )
    )
    for (document_id,) in result.all():
        await render_document(document_id, db)


async def _render_document_standalone(document_id: uuid.UUID) -> None:
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_maker() as db:
            await render_document(document_id, db)
    finally:
        await engine.dispose()


@celery_app.task(name="render.render_document")
def render_document_task(document_id: str) -> None:
    asyncio.run(_render_document_standalone(uuid.UUID(document_id)))
