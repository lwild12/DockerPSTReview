import csv
import io
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_case_member, require_case_reviewer_or_admin
from app.auth.users import current_active_user
from app.db import get_db
from app.models.case import CaseMembership
from app.models.document import Document
from app.models.redaction import Redaction
from app.models.user import User
from app.schemas.redaction import (
    RedactionCreate,
    RedactionLogEntry,
    RedactionRead,
    RedactionUpdate,
)
from app.services.audit import record_audit

router = APIRouter(
    prefix="/cases/{case_id}/documents/{document_id}/redactions", tags=["redactions"]
)
case_log_router = APIRouter(prefix="/cases/{case_id}/redactions", tags=["redactions"])


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


async def _fetch_case_redaction_log(
    case_id: uuid.UUID, db: AsyncSession
) -> list[RedactionLogEntry]:
    result = await db.execute(
        select(Redaction, Document.subject, Document.sender, User.email)
        .join(Document, Document.id == Redaction.document_id)
        .outerjoin(User, User.id == Redaction.created_by_id)
        .where(Document.case_id == case_id)
        .order_by(Document.subject, Redaction.page_number, Redaction.created_at)
    )
    return [
        RedactionLogEntry.model_validate(
            {
                **{c.name: getattr(redaction, c.name) for c in Redaction.__table__.columns},
                "document_subject": subject,
                "document_sender": sender,
                "created_by_email": email,
            }
        )
        for redaction, subject, sender, email in result.all()
    ]


@case_log_router.get("", response_model=list[RedactionLogEntry])
async def list_case_redaction_log(
    case_id: uuid.UUID,
    _membership: CaseMembership = Depends(require_case_member),
    db: AsyncSession = Depends(get_db),
):
    return await _fetch_case_redaction_log(case_id, db)


@case_log_router.get("/export.csv")
async def export_case_redaction_log_csv(
    case_id: uuid.UUID,
    _membership: CaseMembership = Depends(require_case_member),
    db: AsyncSession = Depends(get_db),
):
    entries = await _fetch_case_redaction_log(case_id, db)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "document_id",
            "document_subject",
            "document_sender",
            "page_number",
            "reason",
            "redacted_by",
            "redacted_at",
        ]
    )
    for entry in entries:
        writer.writerow(
            [
                str(entry.document_id),
                entry.document_subject,
                entry.document_sender,
                entry.page_number,
                entry.reason,
                entry.created_by_email or str(entry.created_by_id),
                entry.created_at.isoformat(),
            ]
        )
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="redaction_log_{case_id}.csv"'},
    )
