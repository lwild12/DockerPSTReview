from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.celery_app import celery_app
from app.config import get_settings
from app.models.document import DedupStatus, DocType, Document, Thread
from app.models.importjob import ImportStatus, PSTImportJob
from app.services import pst_extraction, storage
from app.services.dedup import (
    DedupCandidate,
    assign_dedup_status,
    compute_attachment_hash,
    compute_email_hash,
)
from app.services.email_parsing import parse_eml_bytes
from app.services.pst_extraction import ManifestEntry
from app.services.threading_service import ThreadCandidate, assign_threads
from app.tasks.render_tasks import render_documents_for_job

logger = logging.getLogger(__name__)
settings = get_settings()


def _min_datetime() -> datetime:
    return datetime.min.replace(tzinfo=UTC)


def _tz_aware(dt: datetime | None) -> datetime:
    if dt is None:
        return _min_datetime()
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def _participants_key(document: Document) -> str:
    parts = [document.sender, *document.recipients_to, *document.recipients_cc]
    return ",".join(sorted(p.strip().lower() for p in parts if p))


async def _stage_email_entry(entry: ManifestEntry, job: PSTImportJob) -> list[Document]:
    raw = Path(entry.staged_path).read_bytes()
    parsed = parse_eml_bytes(raw)

    attachment_hashes = [compute_attachment_hash(a.content) for a in parsed.attachments]
    content_hash = compute_email_hash(
        parsed.sender,
        parsed.recipients_to,
        parsed.recipients_cc,
        parsed.recipients_bcc,
        parsed.subject,
        parsed.body_text,
        attachment_hashes,
    )

    document = Document(
        id=uuid.uuid4(),
        case_id=job.case_id,
        import_job_id=job.id,
        custodian_id=job.custodian_id,
        doc_type=DocType.email,
        subject=parsed.subject,
        sender=parsed.sender,
        recipients_to=parsed.recipients_to,
        recipients_cc=parsed.recipients_cc,
        recipients_bcc=parsed.recipients_bcc,
        sent_at=parsed.sent_at,
        message_id=parsed.message_id,
        in_reply_to=parsed.in_reply_to,
        references=parsed.references,
        body_text=parsed.body_text,
        body_html=parsed.body_html,
        pst_folder_path=entry.folder_path,
        content_hash=content_hash,
    )

    documents = [document]
    for attachment, att_hash in zip(parsed.attachments, attachment_hashes, strict=True):
        child = Document(
            id=uuid.uuid4(),
            case_id=job.case_id,
            import_job_id=job.id,
            custodian_id=job.custodian_id,
            doc_type=DocType.attachment,
            parent_document_id=document.id,
            subject=attachment.filename,
            mime_type=attachment.mime_type,
            file_size=len(attachment.content),
            content_hash=att_hash,
            pst_folder_path=entry.folder_path,
        )
        child.native_file_path = storage.save_native_file(
            job.case_id, child.id, attachment.filename, attachment.content
        )
        documents.append(child)

    return documents


async def _stage_contact_entry(entry: ManifestEntry, job: PSTImportJob) -> Document:
    data = pst_extraction.parse_vcard_contact(Path(entry.staged_path).read_bytes())
    canonical = "\x1f".join(
        [data.get("full_name", ""), ",".join(sorted(e.lower() for e in data.get("emails", [])))]
    )
    content_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return Document(
        id=uuid.uuid4(),
        case_id=job.case_id,
        import_job_id=job.id,
        custodian_id=job.custodian_id,
        doc_type=DocType.contact,
        subject=data.get("full_name", ""),
        structured_metadata=data,
        pst_folder_path=entry.folder_path,
        content_hash=content_hash,
    )


async def _stage_calendar_entry(entry: ManifestEntry, job: PSTImportJob) -> Document:
    data = json.loads(Path(entry.staged_path).read_text())
    content_hash = hashlib.sha256(json.dumps(data, sort_keys=True).encode("utf-8")).hexdigest()
    return Document(
        id=uuid.uuid4(),
        case_id=job.case_id,
        import_job_id=job.id,
        custodian_id=job.custodian_id,
        doc_type=DocType.calendar,
        subject=data.get("subject", ""),
        structured_metadata=data,
        pst_folder_path=entry.folder_path,
        content_hash=content_hash,
    )


async def _run_dedup(case_id: uuid.UUID, db: AsyncSession) -> int:
    result = await db.execute(select(Document).where(Document.case_id == case_id))
    documents = result.scalars().all()
    candidates = [
        DedupCandidate(
            id=str(d.id), content_hash=d.content_hash, created_at=_tz_aware(d.created_at)
        )
        for d in documents
    ]
    assignments = assign_dedup_status(candidates)
    by_id = {str(d.id): d for d in documents}
    duplicate_count = 0
    for assignment in assignments:
        doc = by_id[assignment.id]
        doc.dedup_status = DedupStatus.duplicate if assignment.is_duplicate else DedupStatus.primary
        doc.duplicate_of_id = (
            uuid.UUID(assignment.duplicate_of_id) if assignment.duplicate_of_id else None
        )
        if assignment.is_duplicate:
            duplicate_count += 1
    await db.commit()
    return duplicate_count


async def _run_threading(case_id: uuid.UUID, db: AsyncSession) -> None:
    result = await db.execute(
        select(Document).where(Document.case_id == case_id, Document.doc_type == DocType.email)
    )
    documents = result.scalars().all()

    candidates = [
        ThreadCandidate(
            id=str(d.id),
            message_id=d.message_id,
            in_reply_to=d.in_reply_to,
            references=d.references or [],
            subject=d.subject,
            participants_key=_participants_key(d),
        )
        for d in documents
    ]
    assignments = assign_threads(candidates)

    groups: dict[str, list[str]] = {}
    for assignment in assignments:
        groups.setdefault(assignment.thread_key, []).append(assignment.id)

    by_id = {str(d.id): d for d in documents}
    threads_by_group: dict[str, Thread] = {}
    for thread_key, members in groups.items():
        if len(members) < 2:
            continue  # a lone email doesn't need a Thread row
        thread = Thread(id=uuid.uuid4(), case_id=case_id)
        member_docs = sorted((by_id[m] for m in members), key=lambda d: _tz_aware(d.sent_at))
        thread.root_document_id = member_docs[0].id
        db.add(thread)
        threads_by_group[thread_key] = thread

    # Flush the Thread inserts before pointing documents.thread_id at them — there's
    # no ORM relationship() between Document and Thread to infer statement ordering
    # from, so without this the FK update can be flushed ahead of the insert.
    await db.flush()

    for thread_key, members in groups.items():
        thread = threads_by_group.get(thread_key)
        if thread is None:
            continue
        for doc_id in members:
            by_id[doc_id].thread_id = thread.id

    await db.commit()


async def run_import_job(import_job_id: uuid.UUID, db: AsyncSession) -> None:
    """Core async pipeline: extract -> parse -> dedup -> thread. Takes a session
    directly so it's callable both from the Celery task below and from tests."""
    job = await db.get(PSTImportJob, import_job_id)
    if job is None:
        logger.error("Import job %s not found", import_job_id)
        return

    job.status = ImportStatus.extracting
    job.started_at = datetime.now(UTC)
    await db.commit()

    staging = storage.staging_dir(job.case_id, job.id)
    try:
        result = await asyncio.to_thread(pst_extraction.extract_pst, job.storage_path, str(staging))
    except Exception as exc:
        logger.exception("PST extraction failed for import job %s", import_job_id)
        job.status = ImportStatus.failed
        job.error_message = str(exc)[:2000]
        await db.commit()
        return

    stats: dict = dict(job.stats or {})
    stats["fallback_used"] = result.fallback_used
    stats["total_items"] = len(result.entries)
    job.status = ImportStatus.parsing
    job.stats = stats
    await db.commit()

    all_documents: list[Document] = []
    parse_errors = 0
    for entry in result.entries:
        try:
            if entry.doc_type == "email":
                all_documents.extend(await _stage_email_entry(entry, job))
            elif entry.doc_type == "contact":
                all_documents.append(await _stage_contact_entry(entry, job))
            elif entry.doc_type == "calendar":
                all_documents.append(await _stage_calendar_entry(entry, job))
        except Exception:
            logger.warning(
                "Failed to stage manifest entry %s, skipping it", entry.id, exc_info=True
            )
            parse_errors += 1

    db.add_all(all_documents)
    await db.flush()

    stats["parse_errors"] = parse_errors
    stats["emails"] = sum(1 for d in all_documents if d.doc_type == DocType.email)
    stats["attachments"] = sum(1 for d in all_documents if d.doc_type == DocType.attachment)
    stats["contacts"] = sum(1 for d in all_documents if d.doc_type == DocType.contact)
    stats["calendar_items"] = sum(1 for d in all_documents if d.doc_type == DocType.calendar)
    job.stats = stats
    job.status = ImportStatus.dedup
    await db.commit()

    stats["duplicates"] = await _run_dedup(job.case_id, db)
    job.stats = stats
    await db.commit()

    await _run_threading(job.case_id, db)

    job.status = ImportStatus.rendering
    await db.commit()
    await render_documents_for_job(job.id, db)

    stats["render_failures"] = await _count_render_failures(job.id, db)
    job.stats = stats
    job.status = (
        ImportStatus.completed
        if parse_errors == 0 and stats["render_failures"] == 0
        else ImportStatus.completed_with_errors
    )
    job.completed_at = datetime.now(UTC)
    await db.commit()

    shutil.rmtree(staging, ignore_errors=True)


async def _count_render_failures(import_job_id: uuid.UUID, db: AsyncSession) -> int:
    result = await db.execute(
        select(Document.id).where(
            Document.import_job_id == import_job_id,
            Document.render_error != "",
        )
    )
    return len(result.all())


async def _run_import_job_standalone(import_job_id: uuid.UUID) -> None:
    # A fresh engine per task invocation avoids Celery worker processes reusing
    # asyncpg connections across the separate event loop each asyncio.run() creates.
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_maker() as db:
            await run_import_job(import_job_id, db)
    finally:
        await engine.dispose()


@celery_app.task(name="ingest.run_import_job")
def run_import_job_task(import_job_id: str) -> None:
    asyncio.run(_run_import_job_standalone(uuid.UUID(import_job_id)))
