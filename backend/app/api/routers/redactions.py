import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_case_member, require_case_reviewer_or_admin
from app.auth.users import current_active_user
from app.db import get_db
from app.models.case import CaseMembership
from app.models.document import Document
from app.models.redaction import Redaction
from app.models.user import User
from app.schemas.redaction import RedactionCreate, RedactionRead, RedactionUpdate
from app.services.audit import record_audit

router = APIRouter(
    prefix="/cases/{case_id}/documents/{document_id}/redactions", tags=["redactions"]
)


async def _get_document_or_404(
    case_id: uuid.UUID, document_id: uuid.UUID, db: AsyncSession
) -> Document:
    document = await db.get(Document, document_id)
    if document is None or document.case_id != case_id:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.get("", response_model=list[RedactionRead])
async def list_redactions(
    case_id: uuid.UUID,
    document_id: uuid.UUID,
    _membership: CaseMembership = Depends(require_case_member),
    db: AsyncSession = Depends(get_db),
):
    await _get_document_or_404(case_id, document_id, db)
    result = await db.execute(
        select(Redaction)
        .where(Redaction.document_id == document_id)
        .order_by(Redaction.page_number, Redaction.created_at)
    )
    return result.scalars().all()


@router.post("", response_model=RedactionRead, status_code=status.HTTP_201_CREATED)
async def create_redaction(
    case_id: uuid.UUID,
    document_id: uuid.UUID,
    payload: RedactionCreate,
    _membership: CaseMembership = Depends(require_case_reviewer_or_admin),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
):
    document = await _get_document_or_404(case_id, document_id, db)
    if payload.page_number < 0 or (
        document.rendered_pdf_page_count and payload.page_number >= document.rendered_pdf_page_count
    ):
        raise HTTPException(status_code=400, detail="page_number is out of range for this document")

    redaction = Redaction(
        id=uuid.uuid4(),
        document_id=document_id,
        page_number=payload.page_number,
        x=payload.x,
        y=payload.y,
        width=payload.width,
        height=payload.height,
        reason=payload.reason,
        color=payload.color,
        created_by_id=user.id,
    )
    db.add(redaction)
    await db.flush()
    record_audit(
        db,
        case_id,
        user.id,
        "redaction.created",
        "document",
        str(document_id),
        {"redaction_id": str(redaction.id), "page_number": redaction.page_number},
    )
    await db.commit()
    await db.refresh(redaction)
    return redaction


@router.patch("/{redaction_id}", response_model=RedactionRead)
async def update_redaction(
    case_id: uuid.UUID,
    document_id: uuid.UUID,
    redaction_id: uuid.UUID,
    payload: RedactionUpdate,
    _membership: CaseMembership = Depends(require_case_reviewer_or_admin),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_document_or_404(case_id, document_id, db)
    redaction = await db.get(Redaction, redaction_id)
    if redaction is None or redaction.document_id != document_id:
        raise HTTPException(status_code=404, detail="Redaction not found")

    for field in ("x", "y", "width", "height", "reason", "color"):
        value = getattr(payload, field)
        if value is not None:
            setattr(redaction, field, value)

    record_audit(
        db,
        case_id,
        user.id,
        "redaction.updated",
        "document",
        str(document_id),
        {"redaction_id": str(redaction.id)},
    )
    await db.commit()
    await db.refresh(redaction)
    return redaction


@router.delete("/{redaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_redaction(
    case_id: uuid.UUID,
    document_id: uuid.UUID,
    redaction_id: uuid.UUID,
    _membership: CaseMembership = Depends(require_case_reviewer_or_admin),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_document_or_404(case_id, document_id, db)
    redaction = await db.get(Redaction, redaction_id)
    if redaction is None or redaction.document_id != document_id:
        raise HTTPException(status_code=404, detail="Redaction not found")
    record_audit(
        db,
        case_id,
        user.id,
        "redaction.deleted",
        "document",
        str(document_id),
        {"redaction_id": str(redaction.id), "page_number": redaction.page_number},
    )
    await db.delete(redaction)
    await db.commit()
