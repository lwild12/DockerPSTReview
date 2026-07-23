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
    user_id: uuid.UUID
    role: CaseRole


class CaseMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    role: CaseRole


class CustodianCreate(BaseModel):
    name: str
    email: str = ""


class CustodianRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str
