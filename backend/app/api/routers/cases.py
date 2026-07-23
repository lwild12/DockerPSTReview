import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_case_admin, require_case_member
from app.auth.users import current_active_user
from app.db import get_db
from app.models.case import Case, CaseMembership, CaseRole, Custodian
from app.models.document import DedupStatus, Document
from app.models.importjob import PSTImportJob
from app.models.review import ReviewSet, ReviewSetDocument
from app.models.user import User
from app.schemas.case import CaseCreate, CaseMemberCreate, CaseMemberRead, CaseRead, CaseStats
from app.services.audit import record_audit

router = APIRouter(prefix="/cases", tags=["cases"])


@router.get("", response_model=list[CaseRead])
async def list_cases(
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Case, CaseMembership.role)
        .join(CaseMembership, CaseMembership.case_id == Case.id)
        .where(CaseMembership.user_id == user.id)
        .order_by(Case.created_at.desc())
    )
    cases = []
    for case, role in result.all():
        item = CaseRead.model_validate(case)
        item.my_role = role
        cases.append(item)
    return cases


@router.post("", response_model=CaseRead, status_code=status.HTTP_201_CREATED)
async def create_case(
    payload: CaseCreate,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
):
    case = Case(name=payload.name, description=payload.description, created_by_id=user.id)
    db.add(case)
    await db.flush()
    membership = CaseMembership(case_id=case.id, user_id=user.id, role=CaseRole.admin)
    db.add(membership)
    record_audit(db, case.id, user.id, "case.created", "case", str(case.id))
    await db.commit()
    await db.refresh(case)
    item = CaseRead.model_validate(case)
    item.my_role = CaseRole.admin
    return item


@router.get("/{case_id}", response_model=CaseRead)
async def get_case(
    case_id: uuid.UUID,
    membership: CaseMembership = Depends(require_case_member),
    db: AsyncSession = Depends(get_db),
):
    case = await db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    item = CaseRead.model_validate(case)
    item.my_role = membership.role
    return item


@router.get("/{case_id}/stats", response_model=CaseStats)
async def get_case_stats(
    case_id: uuid.UUID,
    _membership: CaseMembership = Depends(require_case_member),
    db: AsyncSession = Depends(get_db),
):
    custodians_count = await db.scalar(
        select(func.count()).select_from(Custodian).where(Custodian.case_id == case_id)
    )

    import_status_rows = await db.execute(
        select(PSTImportJob.status, func.count())
        .where(PSTImportJob.case_id == case_id)
        .group_by(PSTImportJob.status)
    )
    import_jobs_by_status = {s.value: count for s, count in import_status_rows.all()}
    import_jobs_total = sum(import_jobs_by_status.values())

    doc_type_rows = await db.execute(
        select(Document.doc_type, func.count())
        .where(Document.case_id == case_id)
        .group_by(Document.doc_type)
    )
    documents_by_type = {doc_type.value: count for doc_type, count in doc_type_rows.all()}
    documents_total = sum(documents_by_type.values())

    dedup_rows = await db.execute(
        select(Document.dedup_status, func.count())
        .where(Document.case_id == case_id)
        .group_by(Document.dedup_status)
    )
    dedup_counts = {s.value: count for s, count in dedup_rows.all()}
    documents_primary = dedup_counts.get("primary", 0)
    documents_duplicate = dedup_counts.get("duplicate", 0)

    documents_rendered = (
        await db.scalar(
            select(func.count())
            .select_from(Document)
            .where(
                Document.case_id == case_id,
                Document.dedup_status == DedupStatus.primary,
                Document.rendered_pdf_page_count > 0,
            )
        )
        or 0
    )
    documents_render_failed = (
        await db.scalar(
            select(func.count())
            .select_from(Document)
            .where(
                Document.case_id == case_id,
                Document.dedup_status == DedupStatus.primary,
                Document.render_error != "",
            )
        )
        or 0
    )
    documents_pending_render = max(
        documents_primary - documents_rendered - documents_render_failed, 0
    )

    review_sets_count = await db.scalar(
        select(func.count()).select_from(ReviewSet).where(ReviewSet.case_id == case_id)
    )

    documents_in_any_review_set = await db.scalar(
        select(func.count(func.distinct(ReviewSetDocument.document_id)))
        .select_from(ReviewSetDocument)
        .join(ReviewSet, ReviewSet.id == ReviewSetDocument.review_set_id)
        .where(ReviewSet.case_id == case_id)
    )

    return CaseStats(
        custodians_count=custodians_count or 0,
        import_jobs_total=import_jobs_total,
        import_jobs_by_status=import_jobs_by_status,
        documents_total=documents_total,
        documents_primary=documents_primary,
        documents_duplicate=documents_duplicate,
        documents_by_type=documents_by_type,
        documents_rendered=documents_rendered,
        documents_render_failed=documents_render_failed,
        documents_pending_render=documents_pending_render,
        review_sets_count=review_sets_count or 0,
        documents_in_any_review_set=documents_in_any_review_set or 0,
    )


@router.get("/{case_id}/members", response_model=list[CaseMemberRead])
async def list_members(
    case_id: uuid.UUID,
    _membership: CaseMembership = Depends(require_case_member),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CaseMembership, User.email)
        .join(User, User.id == CaseMembership.user_id)
        .where(CaseMembership.case_id == case_id)
    )
    return [
        CaseMemberRead(id=m.id, user_id=m.user_id, role=m.role, email=email)
        for m, email in result.all()
    ]


@router.post(
    "/{case_id}/members", response_model=CaseMemberRead, status_code=status.HTTP_201_CREATED
)
async def add_member(
    case_id: uuid.UUID,
    payload: CaseMemberCreate,
    _membership: CaseMembership = Depends(require_case_admin),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
):
    target_user_result = await db.execute(select(User).where(User.email == payload.email))
    target_user = target_user_result.scalar_one_or_none()
    if target_user is None:
        raise HTTPException(status_code=404, detail="No user is registered with that email")

    existing = await db.execute(
        select(CaseMembership).where(
            CaseMembership.case_id == case_id, CaseMembership.user_id == target_user.id
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="User is already a member of this case")
    membership = CaseMembership(case_id=case_id, user_id=target_user.id, role=payload.role)
    db.add(membership)
    await db.flush()
    record_audit(
        db,
        case_id,
        user.id,
        "member.added",
        "case_membership",
        str(membership.id),
        {"user_id": str(target_user.id), "email": target_user.email, "role": payload.role.value},
    )
    await db.commit()
    return CaseMemberRead(
        id=membership.id, user_id=target_user.id, role=membership.role, email=target_user.email
    )


@router.delete("/{case_id}/members/{membership_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    case_id: uuid.UUID,
    membership_id: uuid.UUID,
    _membership: CaseMembership = Depends(require_case_admin),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
):
    target = await db.get(CaseMembership, membership_id)
    if target is None or target.case_id != case_id:
        raise HTTPException(status_code=404, detail="Membership not found")
    record_audit(
        db,
        case_id,
        user.id,
        "member.removed",
        "case_membership",
        str(membership_id),
        {"user_id": str(target.user_id), "role": target.role.value},
    )
    await db.delete(target)
    await db.commit()
