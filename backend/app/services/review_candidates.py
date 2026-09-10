import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import DedupStatus, DocType, Document


async def get_review_candidate_document_ids(
    case_id: uuid.UUID, db: AsyncSession
) -> list[uuid.UUID]:
    """Primary, non-redundant, one-per-near-duplicate-cluster documents -- the
    same set the "Add all documents to a review set" flow computes client-side
    (CaseDetailPage.tsx's addAllToReviewMutation): exact duplicates and
    redundant thread messages (an email whose content is fully quoted in a
    later message) are never useful to send to an LLM, and only one
    representative per near-duplicate cluster is worth scoring.
    """
    stmt = (
        select(
            Document.id,
            Document.doc_type,
            Document.is_inclusive_email,
            Document.near_duplicate_cluster_id,
        )
        .where(Document.case_id == case_id, Document.dedup_status == DedupStatus.primary)
        .order_by(Document.sent_at.asc().nullslast(), Document.created_at.asc(), Document.id)
    )
    rows = (await db.execute(stmt)).all()

    seen_clusters: set[uuid.UUID] = set()
    candidate_ids: list[uuid.UUID] = []
    for doc_id, doc_type, is_inclusive_email, cluster_id in rows:
        if doc_type == DocType.email and not is_inclusive_email:
            continue
        if cluster_id is not None:
            if cluster_id in seen_clusters:
                continue
            seen_clusters.add(cluster_id)
        candidate_ids.append(doc_id)
    return candidate_ids
