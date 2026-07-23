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
from app.models.document import Document
from app.models.tag import DocumentTag, Tag
from app.models.user import User
from app.schemas.tag import TagCreate, TagRead, TagUpdate
from app.services.audit import record_audit

router = APIRouter(prefix="/cases/{case_id}/tags", tags=["tags"])
document_tags_router = APIRouter(
    prefix="/cases/{case_id}/documents/{document_id}/tags", tags=["tags"]
)


@router.get("", response_model=list[TagRead])
async def list_tags(
    case_id: uuid.UUID,
    _membership: CaseMembership = Depends(require_case_member),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Tag).where(Tag.case_id == case_id).order_by(Tag.name))
    return result.scalars().all()


@router.post("", response_model=TagRead, status_code=status.HTTP_201_CREATED)
async def create_tag(
    case_id: uuid.UUID,
    payload: TagCreate,
    _membership: CaseMembership = Depends(require_case_reviewer_or_admin),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(Tag).where(Tag.case_id == case_id, Tag.name == payload.name))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="A tag with this name already exists")
    tag = Tag(
        id=uuid.uuid4(),
        case_id=case_id,
        name=payload.name,
        color=payload.color,
        created_by_id=user.id,
    )
    db.add(tag)
    await db.flush()
    record_audit(db, case_id, user.id, "tag.created", "tag", str(tag.id), {"name": tag.name})
    await db.commit()
    await db.refresh(tag)
    return tag


@router.patch("/{tag_id}", response_model=TagRead)
async def update_tag(
    case_id: uuid.UUID,
    tag_id: uuid.UUID,
    payload: TagUpdate,
    _membership: CaseMembership = Depends(require_case_admin),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
):
    tag = await db.get(Tag, tag_id)
    if tag is None or tag.case_id != case_id:
        raise HTTPException(status_code=404, detail="Tag not found")
    if payload.name is not None:
        tag.name = payload.name
    if payload.color is not None:
        tag.color = payload.color
    record_audit(db, case_id, user.id, "tag.updated", "tag", str(tag.id), {"name": tag.name})
    await db.commit()
    await db.refresh(tag)
    return tag


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(
    case_id: uuid.UUID,
    tag_id: uuid.UUID,
    _membership: CaseMembership = Depends(require_case_admin),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
):
    tag = await db.get(Tag, tag_id)
    if tag is None or tag.case_id != case_id:
        raise HTTPException(status_code=404, detail="Tag not found")
    record_audit(db, case_id, user.id, "tag.deleted", "tag", str(tag.id), {"name": tag.name})
    await db.delete(tag)
    await db.commit()


@document_tags_router.post("/{tag_id}", response_model=TagRead, status_code=status.HTTP_201_CREATED)
async def apply_tag(
    case_id: uuid.UUID,
    document_id: uuid.UUID,
    tag_id: uuid.UUID,
    _membership: CaseMembership = Depends(require_case_reviewer_or_admin),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
):
    document = await db.get(Document, document_id)
    if document is None or document.case_id != case_id:
        raise HTTPException(status_code=404, detail="Document not found")
    tag = await db.get(Tag, tag_id)
    if tag is None or tag.case_id != case_id:
        raise HTTPException(status_code=404, detail="Tag not found")

    existing = await db.execute(
        select(DocumentTag).where(
            DocumentTag.document_id == document_id, DocumentTag.tag_id == tag_id
        )
    )
    if existing.scalar_one_or_none() is None:
        db.add(DocumentTag(document_id=document_id, tag_id=tag_id, tagged_by_id=user.id))
        record_audit(
            db,
            case_id,
            user.id,
            "tag.applied",
            "document",
            str(document_id),
            {"tag_id": str(tag_id)},
        )
        await db.commit()
    return tag


@document_tags_router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_tag(
    case_id: uuid.UUID,
    document_id: uuid.UUID,
    tag_id: uuid.UUID,
    _membership: CaseMembership = Depends(require_case_reviewer_or_admin),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
):
    document = await db.get(Document, document_id)
    if document is None or document.case_id != case_id:
        raise HTTPException(status_code=404, detail="Document not found")
    link = await db.get(DocumentTag, (document_id, tag_id))
    if link is not None:
        record_audit(
            db,
            case_id,
            user.id,
            "tag.removed",
            "document",
            str(document_id),
            {"tag_id": str(tag_id)},
        )
        await db.delete(link)
        await db.commit()
