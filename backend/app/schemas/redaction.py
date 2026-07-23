import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RedactionCreate(BaseModel):
    page_number: int
    x: float
    y: float
    width: float
    height: float
    reason: str = ""
    color: str = "#000000"


class RedactionUpdate(BaseModel):
    x: float | None = None
    y: float | None = None
    width: float | None = None
    height: float | None = None
    reason: str | None = None
    color: str | None = None


class RedactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    page_number: int
    x: float
    y: float
    width: float
    height: float
    reason: str
    color: str
    created_by_id: uuid.UUID
    created_at: datetime


class RedactionLogEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    document_subject: str
    document_sender: str
    page_number: int
    x: float
    y: float
    width: float
    height: float
    reason: str
    color: str
    created_by_id: uuid.UUID
    created_by_email: str | None = None
    created_at: datetime
