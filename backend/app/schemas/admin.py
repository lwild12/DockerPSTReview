import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AdminUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    is_superuser: bool
    is_verified: bool


class AdminUserUpdate(BaseModel):
    is_active: bool | None = None
    is_superuser: bool | None = None


class SystemSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    enable_api_docs: bool
    cookie_secure: bool
    updated_at: datetime
    updated_by_id: uuid.UUID | None


class SystemSettingsUpdate(BaseModel):
    enable_api_docs: bool | None = None
    cookie_secure: bool | None = None
