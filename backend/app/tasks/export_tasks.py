from __future__ import annotations

import asyncio
import csv
import logging
import uuid
import zipfile
from datetime import UTC, datetime

import fitz
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.celery_app import celery_app
from app.config import get_settings
from app.models.document import Document
from app.models.export import ExportDocumentBates, ExportJob, ExportStatus, ExportType
from app.models.redaction import Redaction
from app.services import storage
from app.services.pdf_processing import (
    RedactionRect,
    burn_in_redactions,
    merge_documents,
    stamp_bates,
)

logger = logging.getLogger(__name__)
settings = get_settings()


async def _load_redactions(document_id: uuid.UUID, db: AsyncSession) -> list[RedactionRect]:
    result = await db.execute(select(Redaction).where(Redaction.document_id == document_id))
    return [
        RedactionRect(page_number=r.page_number, x=r.x, y=r.y, width=r.width, height=r.height)
        for r in result.scalars().all()
    ]


async def run_export(export_job_id: uuid.UUID, db: AsyncSession) -> None:
    job = await db.get(ExportJob, export_job_id)
    if job is None:
        logger.error("Export job %s not found", export_job_id)
        return

    job.status = ExportStatus.running
    await db.commit()

    try:
        documents: list[Document] = []
        for raw_id in job.document_ids:
            document = await db.get(Document, uuid.UUID(str(raw_id)))
            if document is not None and document.rendered_pdf_path:
                documents.append(document)

        processed: list[tuple[Document, fitz.Document]] = []
        counter = job.bates_start_number
        bates_rows: list[tuple[Document, str, str, int]] = []

        for document in documents:
            fdoc = fitz.open(
                document.rendered_pdf_path
            )  # fresh copy; never mutate the canonical file
            redactions = await _load_redactions(document.id, db)
            burn_in_redactions(fdoc, redactions)
            if job.apply_bates:
                first, last, counter = stamp_bates(
                    fdoc, job.bates_prefix, counter, job.bates_digit_padding
                )
                bates_rows.append((document, first, last, fdoc.page_count))
            processed.append((document, fdoc))

        output_dir = storage.exports_dir(job.case_id) / str(job.id)
        output_dir.mkdir(parents=True, exist_ok=True)
        bates_by_doc = {row[0].id: row for row in bates_rows}

        if job.export_type == ExportType.production_set:
            file_paths = []
            for document, fdoc in processed:
                if document.id in bates_by_doc:
                    _, first, last, _ = bates_by_doc[document.id]
                    filename = f"{first}-{last}.pdf"
                else:
                    filename = f"{document.id}.pdf"
                path = output_dir / filename
                fdoc.save(str(path))
                file_paths.append(path)

            if bates_rows:
                csv_path = output_dir / "bates_log.csv"
                with open(csv_path, "w", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(
                        ["document_id", "custodian_id", "bates_start", "bates_end", "page_count"]
                    )
                    for document, first, last, page_count in bates_rows:
                        writer.writerow(
                            [
                                str(document.id),
                                str(document.custodian_id or ""),
                                first,
                                last,
                                page_count,
                            ]
                        )
                file_paths.append(csv_path)

            zip_path = output_dir.parent / f"{job.id}.zip"
            with zipfile.ZipFile(zip_path, "w") as zf:
                for path in file_paths:
                    zf.write(path, arcname=path.name)
            job.output_storage_path = str(zip_path)
        else:
            merged = merge_documents([fdoc for _, fdoc in processed])
            output_path = output_dir / "combined.pdf"
            merged.save(str(output_path))
            job.output_storage_path = str(output_path)

        for document, first, last, page_count in bates_rows:
            db.add(
                ExportDocumentBates(
                    id=uuid.uuid4(),
                    export_job_id=job.id,
                    document_id=document.id,
                    bates_start=first,
                    bates_end=last,
                    page_count=page_count,
                )
            )

        job.status = ExportStatus.completed
        job.completed_at = datetime.now(UTC)
        await db.commit()
    except Exception as exc:
        logger.exception("Export job %s failed", export_job_id)
        job.status = ExportStatus.failed
        job.error_message = str(exc)[:2000]
        await db.commit()


async def _run_export_standalone(export_job_id: uuid.UUID) -> None:
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_maker() as db:
            await run_export(export_job_id, db)
    finally:
        await engine.dispose()


@celery_app.task(name="export.run_export")
def run_export_task(export_job_id: str) -> None:
    asyncio.run(_run_export_standalone(uuid.UUID(export_job_id)))
