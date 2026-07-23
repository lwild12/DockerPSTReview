import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.review import ReviewStatus


class ReviewSetCreate(BaseModel):
    name: str
    description: str = ""


class ReviewSetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_id: uuid.UUID
    name: str
    description: str
    created_by_id: uuid.UUID
    created_at: datetime


class ReviewSetAddDocuments(BaseModel):
    document_ids: list[uuid.UUID]


class ReviewSetDocumentUpdate(BaseModel):
    review_status: ReviewStatus | None = None
    assigned_reviewer_id: uuid.UUID | None = None
    notes: str | None = None


class ReviewSetBulkStatusUpdate(BaseModel):
    document_ids: list[uuid.UUID]
    review_status: ReviewStatus


class ReviewSetDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    review_set_id: uuid.UUID
    document_id: uuid.UUID
    review_status: ReviewStatus
    assigned_reviewer_id: uuid.UUID | None
    reviewed_by_id: uuid.UUID | None
    reviewed_at: datetime | None
    notes: str
    document_subject: str = ""
    document_sender: str = ""
    document_doc_type: str = ""
    document_sent_at: datetime | None = None
