import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.case import CaseRole


class CaseCreate(BaseModel):
    name: str
    description: str = ""


class CaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str
    created_by_id: uuid.UUID
    created_at: datetime
    my_role: CaseRole | None = None


class CaseMemberCreate(BaseModel):
    email: str
    role: CaseRole


class CaseMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    email: str
    role: CaseRole


class CustodianCreate(BaseModel):
    name: str
    email: str = ""


class CustodianRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str


class CaseStats(BaseModel):
    custodians_count: int
    import_jobs_total: int
    import_jobs_by_status: dict[str, int]
    documents_total: int
    documents_primary: int
    documents_duplicate: int
    documents_by_type: dict[str, int]
    documents_rendered: int
    documents_render_failed: int
    documents_pending_render: int
    review_sets_count: int
    documents_in_any_review_set: int
