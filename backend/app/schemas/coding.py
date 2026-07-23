import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.coding import CodingFieldType


class CodingFieldCreate(BaseModel):
    name: str
    field_type: CodingFieldType
    options: list[str] = []


class CodingFieldUpdate(BaseModel):
    name: str | None = None
    options: list[str] | None = None


class CodingFieldRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_id: uuid.UUID
    name: str
    field_type: CodingFieldType
    options: list[str]
    created_by_id: uuid.UUID
    created_at: datetime


class DocumentCodingValueSet(BaseModel):
    values: list[str]


class DocumentCodingValueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    coding_field_id: uuid.UUID
    value: str
    set_by_id: uuid.UUID
    set_at: datetime
