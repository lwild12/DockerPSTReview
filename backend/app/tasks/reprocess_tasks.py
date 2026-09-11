from __future__ import annotations

import asyncio
import logging
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.celery_app import celery_app
from app.config import get_settings
from app.models.ai_review import DocumentAiRelevance
from app.models.case import Case
from app.models.coding import DocumentCodingValue
from app.models.document import DocType, Document
from app.models.importjob import ImportStatus, PSTImportJob
from app.models.redaction import Redaction
from app.models.review import ReviewSetDocument, ReviewStatus
from app.models.tag import DocumentTag
from app.services import pst_extraction, storage
from app.tasks.ingest_tasks import ExistingDocumentIndex, _run_dedup, _run_threading, _stage_entry
from app.tasks.render_tasks import render_documents_for_job

logger = logging.getLogger(__name__)
settings = get_settings()


async def _existing_document_index(
    import_job_id: uuid.UUID, db: AsyncSession
) -> tuple[ExistingDocumentIndex, dict[uuid.UUID, Document]]:
    """Documents this import job already produced, indexed for matching
    against a fresh extraction pass. Attachments are indexed under their
    parent's source_item_key (see ExistingDocumentIndex) rather than by
    their own, since only emails/calendar items get a pypff-derived key."""
    result = await db.execute(select(Document).where(Document.import_job_id == import_job_id))
    existing_docs = list(result.scalars().all())
    by_id = {d.id: d for d in existing_docs}

    index = ExistingDocumentIndex()
    for d in existing_docs:
        if d.doc_type != DocType.attachment and d.source_item_key:
            index.by_source_key[d.source_item_key] = d
    for d in existing_docs:
        if d.doc_type != DocType.attachment:
            continue
        parent = by_id.get(d.parent_document_id) if d.parent_document_id else None
        if parent is None or not parent.source_item_key:
            continue
        index.children_by_parent_key.setdefault(parent.source_item_key, {})[d.content_hash] = d
    return index, by_id


async def _documents_with_review_work(
    document_ids: list[uuid.UUID], db: AsyncSession
) -> set[uuid.UUID]:
    """Which of these documents have any human review activity on them --
    a tag, a redaction, a coding value, or a review-set membership that's
    actually been touched (status changed, a note left, or a reviewer
    recorded). A document merely sitting in a review set untouched doesn't
    count -- that's not review work that would be lost."""
    if not document_ids:
        return set()
    has_work: set[uuid.UUID] = set()

    result = await db.execute(
        select(DocumentTag.document_id).where(DocumentTag.document_id.in_(document_ids))
    )
    has_work.update(row[0] for row in result.all())

    result = await db.execute(
        select(Redaction.document_id).where(Redaction.document_id.in_(document_ids))
    )
    has_work.update(row[0] for row in result.all())

    result = await db.execute(
        select(DocumentCodingValue.document_id).where(
            DocumentCodingValue.document_id.in_(document_ids)
        )
    )
    has_work.update(row[0] for row in result.all())

    result = await db.execute(
        select(ReviewSetDocument.document_id).where(
            ReviewSetDocument.document_id.in_(document_ids),
            or_(
                ReviewSetDocument.review_status != ReviewStatus.unreviewed,
                ReviewSetDocument.notes != "",
                ReviewSetDocument.reviewed_by_id.is_not(None),
            ),
        )
    )
    has_work.update(row[0] for row in result.all())

    return has_work


def _delete_document_files(document: Document) -> None:
    for path_str in (document.native_file_path, document.rendered_pdf_path):
        if not path_str:
            continue
        try:
            Path(path_str).unlink(missing_ok=True)
        except OSError:
            logger.warning(
                "Failed to delete file %s for orphaned document %s",
                path_str,
                document.id,
                exc_info=True,
            )


async def reprocess_import_job(job: PSTImportJob, db: AsyncSession) -> dict:
    """Re-run extraction against the PST already stored for this import
    job (no re-upload needed), updating previously-produced documents in
    place where the same underlying PST item can be recognized rather than
    creating duplicates. Mirrors run_import_job's extract -> stage ->
    dedup/thread/render pipeline, but staging matches against
    already-existing documents first."""
    index, by_id = await _existing_document_index(job.id, db)

    staging = storage.staging_dir(job.case_id, job.id) / "reprocess"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)
    try:
        result = await asyncio.to_thread(pst_extraction.extract_pst, job.storage_path, str(staging))

        parse_concurrency = max(1, settings.parse_concurrency)
        semaphore = asyncio.Semaphore(parse_concurrency)

        async def _stage_one(entry):
            async with semaphore:
                return await asyncio.to_thread(_stage_entry, entry, job, index)

        run_started_at = datetime.now(UTC)
        staged = await asyncio.gather(
            *(_stage_one(entry) for entry in result.entries), return_exceptions=True
        )

        all_documents: list[Document] = []
        parse_errors = 0
        for entry, outcome in zip(result.entries, staged, strict=True):
            if isinstance(outcome, BaseException):
                logger.warning(
                    "Failed to restage manifest entry %s during reprocess, skipping it",
                    entry.id,
                    exc_info=outcome,
                )
                parse_errors += 1
            else:
                all_documents.extend(outcome)

        db.add_all(all_documents)
        await db.flush()

        touched_ids = {d.id for d in all_documents}
        new_count = sum(1 for d in all_documents if d.id not in by_id)
        # A document's content_changed_at reflects the most recent change
        # across any reprocess run, not necessarily this one -- comparing
        # against a timestamp captured just before staging isolates only
        # what actually changed just now, for AI-relevance clearing below.
        changed_ids = [
            d.id
            for d in all_documents
            if d.id in by_id and d.content_changed_at and d.content_changed_at >= run_started_at
        ]
        unchanged_count = len(all_documents) - new_count - len(changed_ids)

        if changed_ids:
            await db.execute(
                delete(DocumentAiRelevance).where(DocumentAiRelevance.document_id.in_(changed_ids))
            )

        # Orphans: documents this job produced before that a fresh
        # extraction pass didn't reproduce at all -- e.g. an attachment
        # that's now correctly recognized as an inline image and folded
        # into its email's body instead of getting its own document.
        # Only considered for document types that support matching in the
        # first place (a non-empty source_item_key, or an attachment whose
        # parent has one) -- otherwise every single item would look like
        # an "orphan" every run simply because it was never eligible to be
        # matched (contacts, currently).
        orphan_candidates = []
        for doc_id, d in by_id.items():
            if doc_id in touched_ids:
                continue
            if d.doc_type == DocType.attachment:
                parent = by_id.get(d.parent_document_id) if d.parent_document_id else None
                if parent is None or not parent.source_item_key:
                    continue
            elif not d.source_item_key:
                continue
            orphan_candidates.append(d)

        work_ids = await _documents_with_review_work([d.id for d in orphan_candidates], db)
        orphans_deleted = 0
        orphans_kept = 0
        for d in orphan_candidates:
            if d.id in work_ids:
                orphans_kept += 1
                continue
            _delete_document_files(d)
            await db.delete(d)
            orphans_deleted += 1
        await db.commit()

        await render_documents_for_job(job.id, db)
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    return {
        "total_items": len(result.entries),
        "new": new_count,
        "updated": len(changed_ids),
        "unchanged": unchanged_count,
        "orphans_deleted": orphans_deleted,
        "orphans_kept": orphans_kept,
        "parse_errors": parse_errors,
    }


async def reprocess_case(case_id: uuid.UUID, db: AsyncSession) -> dict:
    """Reprocess every PST previously imported into this case, in place --
    no delete/recreate/re-upload needed to pick up an extraction fix.
    Jobs imported via the readpst fallback (no stable per-item identity
    available -- see Document.source_item_key) are skipped rather than
    silently duplicated; so is any job whose original PST is no longer on
    disk."""
    result = await db.execute(
        select(PSTImportJob).where(
            PSTImportJob.case_id == case_id,
            PSTImportJob.status.in_([ImportStatus.completed, ImportStatus.completed_with_errors]),
        )
    )
    jobs = list(result.scalars().all())

    job_summaries: list[dict] = []
    for job in jobs:
        if not Path(job.storage_path).is_file():
            job_summaries.append(
                {
                    "import_job_id": str(job.id),
                    "uploaded_filename": job.uploaded_filename,
                    "skipped": True,
                    "reason": "the original PST file is no longer on disk",
                }
            )
            continue
        if (job.stats or {}).get("fallback_used"):
            job_summaries.append(
                {
                    "import_job_id": str(job.id),
                    "uploaded_filename": job.uploaded_filename,
                    "skipped": True,
                    "reason": (
                        "imported via the readpst fallback, which doesn't support "
                        "matching against a prior import -- reprocessing it would "
                        "create duplicates rather than update existing documents"
                    ),
                }
            )
            continue
        try:
            stats = await reprocess_import_job(job, db)
        except Exception as exc:
            logger.exception("Reprocessing import job %s failed", job.id)
            await db.rollback()
            job_summaries.append(
                {
                    "import_job_id": str(job.id),
                    "uploaded_filename": job.uploaded_filename,
                    "skipped": True,
                    "reason": f"reprocessing failed: {exc}"[:500],
                }
            )
            continue
        job_summaries.append(
            {
                "import_job_id": str(job.id),
                "uploaded_filename": job.uploaded_filename,
                "skipped": False,
                **stats,
            }
        )

    await _run_dedup(case_id, db)
    await _run_threading(case_id, db)

    return {"jobs": job_summaries}


async def _reprocess_case_standalone(case_id: uuid.UUID) -> None:
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_maker() as db:
            case = await db.get(Case, case_id)
            if case is None:
                logger.error("Case %s not found for reprocess", case_id)
                return
            case.reprocess_last_run_started_at = datetime.now(UTC)
            case.reprocess_last_run_completed_at = None
            await db.commit()

            summary = await reprocess_case(case_id, db)

            case = await db.get(Case, case_id)
            case.reprocess_last_run_summary = summary
            case.reprocess_last_run_completed_at = datetime.now(UTC)
            await db.commit()
    finally:
        await engine.dispose()


@celery_app.task(name="ingest.reprocess_case")
def reprocess_case_task(case_id: str) -> None:
    asyncio.run(_reprocess_case_standalone(uuid.UUID(case_id)))
