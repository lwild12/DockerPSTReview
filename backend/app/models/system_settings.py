import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import UUIDPKMixin


class SystemSettings(UUIDPKMixin, Base):
    """Singleton table: exactly one row, created by migration."""

    __tablename__ = "system_settings"

    enable_api_docs: Mapped[bool] = mapped_column(Boolean, default=False)
    cookie_secure: Mapped[bool] = mapped_column(Boolean, default=False)
    oidc_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    oidc_issuer_url: Mapped[str] = mapped_column(String(500), default="")
    oidc_client_id: Mapped[str] = mapped_column(String(255), default="")
    # Fernet-encrypted at rest; see app/services/encryption.py. Never returned by the API.
    oidc_client_secret_encrypted: Mapped[str] = mapped_column(String(2000), default="")
    oidc_display_name: Mapped[str] = mapped_column(String(100), default="SSO")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
