import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routers.documents import _TAGS_OPTION, _list_item
from app.auth.dependencies import require_case_admin, require_case_member
from app.db import get_db
from app.models.case import Case, CaseMembership
from app.models.document import DedupStatus, DocType, Document, NearDuplicateCluster
from app.schemas.analytics import CaseAnalyticsSummary, NearDuplicateClusterRead
from app.schemas.document import DocumentListItem
from app.tasks.analytics_tasks import run_case_analytics

router = APIRouter(prefix="/cases/{case_id}/analytics", tags=["analytics"])
clusters_router = APIRouter(prefix="/cases/{case_id}/near-duplicate-clusters", tags=["analytics"])


async def _summary(case: Case, db: AsyncSession) -> CaseAnalyticsSummary:
    cluster_count = await db.scalar(
        select(func.count())
        .select_from(NearDuplicateCluster)
        .where(NearDuplicateCluster.case_id == case.id)
    )
    non_inclusive_count = await db.scalar(
        select(func.count())
        .select_from(Document)
        .where(
            Document.case_id == case.id,
            Document.doc_type == DocType.email,
            Document.dedup_status == DedupStatus.primary,
            Document.is_inclusive_email.is_(False),
        )
    )
    return CaseAnalyticsSummary(
        computed_at=case.analytics_computed_at,
        near_duplicate_cluster_count=cluster_count or 0,
        non_inclusive_email_count=non_inclusive_count or 0,
    )


@router.get("", response_model=CaseAnalyticsSummary)
async def get_case_analytics(
    case_id: uuid.UUID,
    _membership: CaseMembership = Depends(require_case_member),
    db: AsyncSession = Depends(get_db),
):
    case = await db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return await _summary(case, db)


@router.post("/recompute", response_model=CaseAnalyticsSummary)
async def recompute_case_analytics(
    case_id: uuid.UUID,
    _membership: CaseMembership = Depends(require_case_admin),
    db: AsyncSession = Depends(get_db),
):
    case = await db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    await run_case_analytics(case_id, db)
    await db.refresh(case)
    return await _summary(case, db)


@clusters_router.get("", response_model=list[NearDuplicateClusterRead])
async def list_near_duplicate_clusters(
    case_id: uuid.UUID,
    _membership: CaseMembership = Depends(require_case_member),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(
            NearDuplicateCluster.id,
            func.count(Document.id).label("member_count"),
        )
        .join(Document, Document.near_duplicate_cluster_id == NearDuplicateCluster.id)
        .where(NearDuplicateCluster.case_id == case_id)
        .group_by(NearDuplicateCluster.id)
        .order_by(func.count(Document.id).desc())
    )
    return [
        NearDuplicateClusterRead(id=row.id, member_count=row.member_count) for row in result.all()
    ]


@clusters_router.get("/{cluster_id}/documents", response_model=list[DocumentListItem])
async def list_near_duplicate_cluster_documents(
    case_id: uuid.UUID,
    cluster_id: uuid.UUID,
    _membership: CaseMembership = Depends(require_case_member),
    db: AsyncSession = Depends(get_db),
):
    cluster = await db.get(NearDuplicateCluster, cluster_id)
    if cluster is None or cluster.case_id != case_id:
        raise HTTPException(status_code=404, detail="Near-duplicate cluster not found")
    result = await db.execute(
        select(Document)
        .where(Document.near_duplicate_cluster_id == cluster_id, Document.case_id == case_id)
        .order_by(Document.subject)
        .options(_TAGS_OPTION)
    )
    return [_list_item(d) for d in result.scalars().unique().all()]
