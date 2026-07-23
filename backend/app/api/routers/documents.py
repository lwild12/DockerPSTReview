import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import require_case_member
from app.db import get_db
from app.models.case import CaseMembership
from app.models.document import DedupStatus, DocType, Document, Thread
from app.models.tag import DocumentTag
from app.schemas.document import DocumentDetail, DocumentListItem, ThreadSibling
from app.schemas.tag import TagRead

router = APIRouter(prefix="/cases/{case_id}/documents", tags=["documents"])
threads_router = APIRouter(prefix="/cases/{case_id}/threads", tags=["documents"])

_TAGS_OPTION = selectinload(Document.tags).selectinload(DocumentTag.tag)


def _tags_of(document: Document) -> list[TagRead]:
    # Built before validation, not assigned after: Pydantic's from_attributes
    # validation runs on document.tags (list[DocumentTag]) the moment
    # model_validate(document) is called, which fails since DocumentTag isn't
    # shaped like TagRead — so the transformed value must go in *before* that.
    return [TagRead.model_validate(dt.tag) for dt in document.tags]


def _list_item(document: Document) -> DocumentListItem:
    return DocumentListItem.model_validate(
        {
            **{c.name: getattr(document, c.name) for c in Document.__table__.columns},
            "tags": _tags_of(document),
        }
    )


def _detail(document: Document) -> DocumentDetail:
    return DocumentDetail.model_validate(
        {
            **{c.name: getattr(document, c.name) for c in Document.__table__.columns},
            "tags": _tags_of(document),
        }
    )


@router.get("", response_model=list[DocumentListItem])
async def list_documents(
    case_id: uuid.UUID,
    doc_type: DocType | None = None,
    custodian_id: uuid.UUID | None = None,
    dedup_status: DedupStatus | None = None,
    thread_id: uuid.UUID | None = None,
    tag_id: uuid.UUID | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = 50,
    _membership: CaseMembership = Depends(require_case_member),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Document).where(Document.case_id == case_id).options(_TAGS_OPTION)
    if doc_type is not None:
        stmt = stmt.where(Document.doc_type == doc_type)
    if custodian_id is not None:
        stmt = stmt.where(Document.custodian_id == custodian_id)
    if dedup_status is not None:
        stmt = stmt.where(Document.dedup_status == dedup_status)
    if thread_id is not None:
        stmt = stmt.where(Document.thread_id == thread_id)
    if tag_id is not None:
        stmt = stmt.join(DocumentTag, DocumentTag.document_id == Document.id).where(
            DocumentTag.tag_id == tag_id
        )
    tsquery = None
    if q:
        pattern = f"%{q}%"
        tsquery = func.websearch_to_tsquery("english", q)
        stmt = stmt.where(
            or_(
                Document.search_vector.op("@@")(tsquery),
                Document.subject.ilike(pattern),
                Document.sender.ilike(pattern),
                Document.body_text.ilike(pattern),
                Document.ocr_text.ilike(pattern),
            )
        )
    if tsquery is not None:
        # Full-text hits rank by relevance first; the ILIKE-only fallback matches
        # (substrings a stemmed tsquery wouldn't catch) sort after via ts_rank's 0.
        stmt = stmt.order_by(
            func.ts_rank(Document.search_vector, tsquery).desc(),
            Document.sent_at.desc().nullslast(),
        )
    else:
        stmt = stmt.order_by(Document.sent_at.desc().nullslast(), Document.created_at.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    documents = result.scalars().unique().all()
    return [_list_item(d) for d in documents]


@router.get("/{document_id}", response_model=DocumentDetail)
async def get_document(
    case_id: uuid.UUID,
    document_id: uuid.UUID,
    _membership: CaseMembership = Depends(require_case_member),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Document)
        .where(Document.id == document_id, Document.case_id == case_id)
        .options(_TAGS_OPTION)
    )
    result = await db.execute(stmt)
    document = result.scalars().unique().one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return _detail(document)


@router.get("/{document_id}/pdf")
async def get_document_pdf(
    case_id: uuid.UUID,
    document_id: uuid.UUID,
    _membership: CaseMembership = Depends(require_case_member),
    db: AsyncSession = Depends(get_db),
):
    document = await db.get(Document, document_id)
    if document is None or document.case_id != case_id:
        raise HTTPException(status_code=404, detail="Document not found")
    if not document.rendered_pdf_path:
        raise HTTPException(status_code=404, detail="Document has not been rendered yet")
    return FileResponse(document.rendered_pdf_path, media_type="application/pdf")


@threads_router.get("/{thread_id}/documents", response_model=list[ThreadSibling])
async def list_thread_documents(
    case_id: uuid.UUID,
    thread_id: uuid.UUID,
    _membership: CaseMembership = Depends(require_case_member),
    db: AsyncSession = Depends(get_db),
):
    thread = await db.get(Thread, thread_id)
    if thread is None or thread.case_id != case_id:
        raise HTTPException(status_code=404, detail="Thread not found")
    result = await db.execute(
        select(Document)
        .where(Document.thread_id == thread_id, Document.case_id == case_id)
        .order_by(Document.sent_at.asc().nullslast())
    )
    return result.scalars().all()
