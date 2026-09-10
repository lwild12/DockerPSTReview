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
    enable_api_docs: bool
    cookie_secure: bool
    registration_enabled: bool
    oidc_enabled: bool
    oidc_issuer_url: str
    oidc_client_id: str
    oidc_client_secret_set: bool
    oidc_display_name: str
    ollama_base_url: str
    ollama_model: str
    ollama_api_key_set: bool
    ai_review_concurrency: int
    ollama_log_requests: bool
    updated_at: datetime
    updated_by_id: uuid.UUID | None


class SystemSettingsUpdate(BaseModel):
    enable_api_docs: bool | None = None
    cookie_secure: bool | None = None
    registration_enabled: bool | None = None
    oidc_enabled: bool | None = None
    oidc_issuer_url: str | None = None
    oidc_client_id: str | None = None
    # Write-only. Omit to leave the stored secret unchanged; pass "" to clear it.
    oidc_client_secret: str | None = None
    oidc_display_name: str | None = None
    ollama_base_url: str | None = None
    ollama_model: str | None = None
    # Write-only, same convention as oidc_client_secret above.
    ollama_api_key: str | None = None
    ai_review_concurrency: int | None = None
    ollama_log_requests: bool | None = None
