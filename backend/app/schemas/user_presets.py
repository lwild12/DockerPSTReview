import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserTagPresetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    color: str
    created_at: datetime


class UserRedactionReasonPresetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reason: str
    created_at: datetime
