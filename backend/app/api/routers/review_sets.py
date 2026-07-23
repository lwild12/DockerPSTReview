import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_case_member, require_case_reviewer_or_admin
from app.auth.users import current_active_user
from app.db import get_db
from app.models.case import CaseMembership
from app.models.document import Document
from app.models.review import ReviewSet, ReviewSetDocument
from app.models.user import User
from app.schemas.review import (
    ReviewSetAddDocuments,
    ReviewSetCreate,
    ReviewSetDocumentRead,
    ReviewSetDocumentUpdate,
    ReviewSetRead,
)
from app.services.audit import record_audit

router = APIRouter(prefix="/cases/{case_id}/review-sets", tags=["review-sets"])


def _to_read(link: ReviewSetDocument, document: Document) -> ReviewSetDocumentRead:
    return ReviewSetDocumentRead(
        id=link.id,
        review_set_id=link.review_set_id,
        document_id=link.document_id,
        review_status=link.review_status,
        assigned_reviewer_id=link.assigned_reviewer_id,
        reviewed_by_id=link.reviewed_by_id,
        reviewed_at=link.reviewed_at,
        notes=link.notes,
        document_subject=document.subject,
        document_sender=document.sender,
        document_doc_type=document.doc_type.value,
        document_sent_at=document.sent_at,
    )


@router.get("", response_model=list[ReviewSetRead])
async def list_review_sets(
    case_id: uuid.UUID,
    _membership: CaseMembership = Depends(require_case_member),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ReviewSet).where(ReviewSet.case_id == case_id).order_by(ReviewSet.created_at.desc())
    )
    return result.scalars().all()


@router.post("", response_model=ReviewSetRead, status_code=status.HTTP_201_CREATED)
async def create_review_set(
    case_id: uuid.UUID,
    payload: ReviewSetCreate,
    _membership: CaseMembership = Depends(require_case_reviewer_or_admin),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
):
    review_set = ReviewSet(
        id=uuid.uuid4(),
        case_id=case_id,
        name=payload.name,
        description=payload.description,
        created_by_id=user.id,
    )
    db.add(review_set)
    await db.flush()
    record_audit(
        db,
        case_id,
        user.id,
        "review_set.created",
        "review_set",
        str(review_set.id),
        {"name": review_set.name},
    )
    await db.commit()
    await db.refresh(review_set)
    return review_set


@router.get("/{review_set_id}", response_model=ReviewSetRead)
async def get_review_set(
    case_id: uuid.UUID,
    review_set_id: uuid.UUID,
    _membership: CaseMembership = Depends(require_case_member),
    db: AsyncSession = Depends(get_db),
):
    review_set = await db.get(ReviewSet, review_set_id)
    if review_set is None or review_set.case_id != case_id:
        raise HTTPException(status_code=404, detail="Review set not found")
    return review_set


@router.get("/{review_set_id}/documents", response_model=list[ReviewSetDocumentRead])
async def list_review_set_documents(
    case_id: uuid.UUID,
    review_set_id: uuid.UUID,
    _membership: CaseMembership = Depends(require_case_member),
    db: AsyncSession = Depends(get_db),
):
    review_set = await db.get(ReviewSet, review_set_id)
    if review_set is None or review_set.case_id != case_id:
        raise HTTPException(status_code=404, detail="Review set not found")
    result = await db.execute(
        select(ReviewSetDocument, Document)
        .join(Document, Document.id == ReviewSetDocument.document_id)
        .where(ReviewSetDocument.review_set_id == review_set_id)
    )
    return [_to_read(link, document) for link, document in result.all()]


@router.post(
    "/{review_set_id}/documents",
    response_model=list[ReviewSetDocumentRead],
    status_code=status.HTTP_201_CREATED,
)
async def add_documents_to_review_set(
    case_id: uuid.UUID,
    review_set_id: uuid.UUID,
    payload: ReviewSetAddDocuments,
    _membership: CaseMembership = Depends(require_case_reviewer_or_admin),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
):
    review_set = await db.get(ReviewSet, review_set_id)
    if review_set is None or review_set.case_id != case_id:
        raise HTTPException(status_code=404, detail="Review set not found")

    existing_result = await db.execute(
        select(ReviewSetDocument.document_id).where(
            ReviewSetDocument.review_set_id == review_set_id
        )
    )
    already_added = {row[0] for row in existing_result.all()}

    valid_docs = await db.execute(
        select(Document).where(Document.id.in_(payload.document_ids), Document.case_id == case_id)
    )
    valid_documents = {d.id: d for d in valid_docs.scalars().all()}

    created: list[tuple[ReviewSetDocument, Document]] = []
    for document_id in payload.document_ids:
        if document_id not in valid_documents or document_id in already_added:
            continue
        link = ReviewSetDocument(
            id=uuid.uuid4(), review_set_id=review_set_id, document_id=document_id
        )
        db.add(link)
        created.append((link, valid_documents[document_id]))

    if created:
        record_audit(
            db,
            case_id,
            user.id,
            "review_set.documents_added",
            "review_set",
            str(review_set_id),
            {"document_ids": [str(link.document_id) for link, _ in created]},
        )
    await db.commit()
    return [_to_read(link, document) for link, document in created]


@router.patch("/{review_set_id}/documents/{document_id}", response_model=ReviewSetDocumentRead)
async def update_review_set_document(
    case_id: uuid.UUID,
    review_set_id: uuid.UUID,
    document_id: uuid.UUID,
    payload: ReviewSetDocumentUpdate,
    _membership: CaseMembership = Depends(require_case_reviewer_or_admin),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
):
    review_set = await db.get(ReviewSet, review_set_id)
    if review_set is None or review_set.case_id != case_id:
        raise HTTPException(status_code=404, detail="Review set not found")

    result = await db.execute(
        select(ReviewSetDocument).where(
            ReviewSetDocument.review_set_id == review_set_id,
            ReviewSetDocument.document_id == document_id,
        )
    )
    link = result.scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=404, detail="Document is not in this review set")

    if payload.review_status is not None:
        link.review_status = payload.review_status
        link.reviewed_by_id = user.id
        link.reviewed_at = datetime.now(UTC)
    if payload.assigned_reviewer_id is not None:
        link.assigned_reviewer_id = payload.assigned_reviewer_id
    if payload.notes is not None:
        link.notes = payload.notes

    record_audit(
        db,
        case_id,
        user.id,
        "review_set_document.updated",
        "document",
        str(document_id),
        {"review_set_id": str(review_set_id), "review_status": link.review_status.value},
    )
    await db.commit()
    document = await db.get(Document, document_id)
    return _to_read(link, document)
