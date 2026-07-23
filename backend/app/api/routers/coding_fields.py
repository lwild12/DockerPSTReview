import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    require_case_admin,
    require_case_member,
    require_case_reviewer_or_admin,
)
from app.auth.users import current_active_user
from app.db import get_db
from app.models.case import CaseMembership
from app.models.coding import CodingField, CodingFieldType, DocumentCodingValue
from app.models.document import Document
from app.models.user import User
from app.schemas.coding import (
    CodingFieldCreate,
    CodingFieldRead,
    CodingFieldUpdate,
    DocumentCodingValueRead,
    DocumentCodingValueSet,
)
from app.services.audit import record_audit

router = APIRouter(prefix="/cases/{case_id}/coding-fields", tags=["coding"])
document_coding_router = APIRouter(
    prefix="/cases/{case_id}/documents/{document_id}/coding-values", tags=["coding"]
)


@router.get("", response_model=list[CodingFieldRead])
async def list_coding_fields(
    case_id: uuid.UUID,
    _membership: CaseMembership = Depends(require_case_member),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CodingField).where(CodingField.case_id == case_id).order_by(CodingField.name)
    )
    return result.scalars().all()


@router.post("", response_model=CodingFieldRead, status_code=status.HTTP_201_CREATED)
async def create_coding_field(
    case_id: uuid.UUID,
    payload: CodingFieldCreate,
    _membership: CaseMembership = Depends(require_case_admin),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if not payload.options:
        raise HTTPException(status_code=422, detail="A coding field needs at least one option")
    existing = await db.execute(
        select(CodingField).where(CodingField.case_id == case_id, CodingField.name == payload.name)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="A coding field with this name already exists")
    field = CodingField(
        id=uuid.uuid4(),
        case_id=case_id,
        name=payload.name,
        field_type=payload.field_type,
        options=payload.options,
        created_by_id=user.id,
    )
    db.add(field)
    await db.flush()
    record_audit(db, case_id, user.id, "coding_field.created", "coding_field", str(field.id), {"name": field.name})
    await db.commit()
    await db.refresh(field)
    return field


@router.patch("/{field_id}", response_model=CodingFieldRead)
async def update_coding_field(
    case_id: uuid.UUID,
    field_id: uuid.UUID,
    payload: CodingFieldUpdate,
    _membership: CaseMembership = Depends(require_case_admin),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
):
    field = await db.get(CodingField, field_id)
    if field is None or field.case_id != case_id:
        raise HTTPException(status_code=404, detail="Coding field not found")
    if payload.name is not None:
        field.name = payload.name
    if payload.options is not None:
        if not payload.options:
            raise HTTPException(status_code=422, detail="A coding field needs at least one option")
        field.options = payload.options
    record_audit(db, case_id, user.id, "coding_field.updated", "coding_field", str(field.id), {"name": field.name})
    await db.commit()
    await db.refresh(field)
    return field


@router.delete("/{field_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_coding_field(
    case_id: uuid.UUID,
    field_id: uuid.UUID,
    _membership: CaseMembership = Depends(require_case_admin),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
):
    field = await db.get(CodingField, field_id)
    if field is None or field.case_id != case_id:
        raise HTTPException(status_code=404, detail="Coding field not found")
    record_audit(db, case_id, user.id, "coding_field.deleted", "coding_field", str(field.id), {"name": field.name})
    await db.delete(field)
    await db.commit()


@document_coding_router.get("", response_model=list[DocumentCodingValueRead])
async def list_document_coding_values(
    case_id: uuid.UUID,
    document_id: uuid.UUID,
    _membership: CaseMembership = Depends(require_case_member),
    db: AsyncSession = Depends(get_db),
):
    document = await db.get(Document, document_id)
    if document is None or document.case_id != case_id:
        raise HTTPException(status_code=404, detail="Document not found")
    result = await db.execute(
        select(DocumentCodingValue).where(DocumentCodingValue.document_id == document_id)
    )
    return result.scalars().all()


@document_coding_router.put("/{field_id}", response_model=list[DocumentCodingValueRead])
async def set_document_coding_value(
    case_id: uuid.UUID,
    document_id: uuid.UUID,
    field_id: uuid.UUID,
    payload: DocumentCodingValueSet,
    _membership: CaseMembership = Depends(require_case_reviewer_or_admin),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
):
    document = await db.get(Document, document_id)
    if document is None or document.case_id != case_id:
        raise HTTPException(status_code=404, detail="Document not found")
    field = await db.get(CodingField, field_id)
    if field is None or field.case_id != case_id:
        raise HTTPException(status_code=404, detail="Coding field not found")

    values = list(dict.fromkeys(payload.values))
    invalid = [v for v in values if v not in field.options]
    if invalid:
        raise HTTPException(status_code=422, detail=f"Not a valid option for this field: {invalid[0]}")
    if field.field_type == CodingFieldType.single_select and len(values) > 1:
        raise HTTPException(status_code=422, detail="This field only allows a single value")

    existing = await db.execute(
        select(DocumentCodingValue).where(
            DocumentCodingValue.document_id == document_id,
            DocumentCodingValue.coding_field_id == field_id,
        )
    )
    for row in existing.scalars().all():
        await db.delete(row)
    await db.flush()

    created = [
        DocumentCodingValue(
            id=uuid.uuid4(),
            document_id=document_id,
            coding_field_id=field_id,
            value=value,
            set_by_id=user.id,
        )
        for value in values
    ]
    db.add_all(created)
    record_audit(
        db,
        case_id,
        user.id,
        "coding_value.set",
        "document",
        str(document_id),
        {"field_id": str(field_id), "values": values},
    )
    await db.commit()
    for row in created:
        await db.refresh(row)
    return created
