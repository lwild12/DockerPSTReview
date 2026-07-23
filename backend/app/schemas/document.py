import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.document import DedupStatus, DocType, OcrStatus
from app.schemas.tag import TagRead


class DocumentListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    doc_type: DocType
    subject: str
    sender: str
    sent_at: datetime | None
    custodian_id: uuid.UUID | None
    thread_id: uuid.UUID | None
    parent_document_id: uuid.UUID | None
    dedup_status: DedupStatus
    rendered_pdf_page_count: int
    render_error: str
    ocr_status: OcrStatus
    tags: list[TagRead] = []


class DocumentDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_id: uuid.UUID
    import_job_id: uuid.UUID | None
    custodian_id: uuid.UUID | None
    doc_type: DocType
    parent_document_id: uuid.UUID | None
    thread_id: uuid.UUID | None
    subject: str
    sender: str
    recipients_to: list[str]
    recipients_cc: list[str]
    recipients_bcc: list[str]
    sent_at: datetime | None
    message_id: str
    in_reply_to: str
    references: list[str]
    body_text: str
    body_html: str
    structured_metadata: dict
    pst_folder_path: str
    mime_type: str
    file_size: int
    rendered_pdf_page_count: int
    render_error: str
    content_hash: str
    dedup_status: DedupStatus
    duplicate_of_id: uuid.UUID | None
    created_at: datetime
    ocr_text: str
    ocr_status: OcrStatus
    ocr_error: str
    tags: list[TagRead] = []


class ThreadSibling(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subject: str
    sender: str
    sent_at: datetime | None
