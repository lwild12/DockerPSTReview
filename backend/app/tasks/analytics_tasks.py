from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

import fitz
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import Case
from app.models.document import DedupStatus, DocType, Document, NearDuplicateCluster
from app.services.inclusiveness import ThreadMemberCandidate, compute_inclusiveness
from app.services.near_duplicates import NearDupCandidate, compute_near_duplicate_clusters

logger = logging.getLogger(__name__)


def _extract_text_for_analytics(document: Document) -> str:
    """Email uses its parsed body; attachments use OCR text if any, else the
    rendered PDF's own text layer (extracted live, not persisted -- this is
    only needed for this one-off comparison)."""
    if document.doc_type == DocType.email:
        return document.body_text
    if document.ocr_text:
        return document.ocr_text
    if not document.rendered_pdf_path:
        return ""
    try:
        with fitz.open(document.rendered_pdf_path) as opened:
            return "\n".join(page.get_text() for page in opened)
    except Exception:
        logger.warning(
            "Failed to extract text for near-dup analytics on document %s",
            document.id,
            exc_info=True,
        )
        return ""


async def _compute_inclusiveness(case_id: uuid.UUID, db: AsyncSession) -> int:
    result = await db.execute(
        select(Document).where(
            Document.case_id == case_id,
            Document.doc_type == DocType.email,
            Document.dedup_status == DedupStatus.primary,
        )
    )
    documents = result.scalars().all()

    by_thread: dict[uuid.UUID, list[Document]] = {}
    for doc in documents:
        if doc.thread_id is None:
            doc.is_inclusive_email = True
        else:
            by_thread.setdefault(doc.thread_id, []).append(doc)

    non_inclusive_count = 0
    for members in by_thread.values():
        candidates = [
            ThreadMemberCandidate(
                id=str(d.id),
                message_id=d.message_id,
                in_reply_to=d.in_reply_to,
                references=d.references or [],
            )
            for d in members
        ]
        results = {r.id: r.is_inclusive for r in compute_inclusiveness(candidates)}
        for d in members:
            d.is_inclusive_email = results[str(d.id)]
            if not d.is_inclusive_email:
                non_inclusive_count += 1
    return non_inclusive_count


async def _compute_near_duplicates(case_id: uuid.UUID, db: AsyncSession) -> int:
    # Recompute is wholesale, not incremental: clear every prior assignment
    # (and stale cluster rows) for the case before rebuilding from scratch.
    await db.execute(
        update(Document).where(Document.case_id == case_id).values(near_duplicate_cluster_id=None)
    )
    await db.execute(delete(NearDuplicateCluster).where(NearDuplicateCluster.case_id == case_id))

    result = await db.execute(
        select(Document).where(
            Document.case_id == case_id,
            Document.doc_type.in_([DocType.email, DocType.attachment]),
            Document.dedup_status == DedupStatus.primary,
        )
    )
    documents = result.scalars().all()
    by_id = {str(d.id): d for d in documents}

    candidates = [
        NearDupCandidate(id=str(d.id), text=_extract_text_for_analytics(d)) for d in documents
    ]
    assignments = compute_near_duplicate_clusters(candidates)

    groups: dict[str, list[str]] = {}
    for assignment in assignments:
        if assignment.cluster_key is not None:
            groups.setdefault(assignment.cluster_key, []).append(assignment.id)

    clusters_by_key: dict[str, NearDuplicateCluster] = {}
    for key in groups:
        cluster = NearDuplicateCluster(id=uuid.uuid4(), case_id=case_id)
        db.add(cluster)
        clusters_by_key[key] = cluster

    # Flush the cluster inserts before pointing documents at them -- there's no
    # relationship() between Document and NearDuplicateCluster to infer statement
    # ordering from, same hazard noted for thread assignment in ingest_tasks.py.
    await db.flush()

    for key, members in groups.items():
        cluster = clusters_by_key[key]
        for doc_id in members:
            by_id[doc_id].near_duplicate_cluster_id = cluster.id

    return len(groups)


async def run_case_analytics(case_id: uuid.UUID, db: AsyncSession) -> dict[str, int]:
    """On-demand recompute of near-duplicate clusters and email-thread
    inclusiveness for a case. Safe to re-run: each call fully replaces the
    prior results rather than updating them incrementally."""
    case = await db.get(Case, case_id)
    if case is None:
        logger.error("Case %s not found for analytics run", case_id)
        return {"near_duplicate_clusters": 0, "non_inclusive_emails": 0}

    non_inclusive_count = await _compute_inclusiveness(case_id, db)
    cluster_count = await _compute_near_duplicates(case_id, db)

    case.analytics_computed_at = datetime.now(UTC)
    await db.commit()
    return {"near_duplicate_clusters": cluster_count, "non_inclusive_emails": non_inclusive_count}
