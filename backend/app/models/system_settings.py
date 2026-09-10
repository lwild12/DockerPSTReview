import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import UUIDPKMixin


class SystemSettings(UUIDPKMixin, Base):
    """Singleton table: exactly one row, created by migration."""

    __tablename__ = "system_settings"

    enable_api_docs: Mapped[bool] = mapped_column(Boolean, default=False)
    cookie_secure: Mapped[bool] = mapped_column(Boolean, default=False)
    registration_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    oidc_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    oidc_issuer_url: Mapped[str] = mapped_column(String(500), default="")
    oidc_client_id: Mapped[str] = mapped_column(String(255), default="")
    # Fernet-encrypted at rest; see app/services/encryption.py. Never returned by the API.
    oidc_client_secret_encrypted: Mapped[str] = mapped_column(String(2000), default="")
    oidc_display_name: Mapped[str] = mapped_column(String(100), default="SSO")
    ollama_base_url: Mapped[str] = mapped_column(String(500), default="")
    ollama_model: Mapped[str] = mapped_column(String(255), default="")
    # Fernet-encrypted at rest, same as oidc_client_secret_encrypted. Optional --
    # most self-hosted Ollama is unauthenticated; this is forward-compat for a
    # hosted proxy that needs one.
    ollama_api_key_encrypted: Mapped[str] = mapped_column(String(2000), default="")
    # Kept alongside the endpoint/model rather than in the env-var Settings
    # (unlike render/parse concurrency, which tune CPU-bound local work sized
    # to the host machine at deploy time): the right value here is a property
    # of the external Ollama server's capacity, which the same admin
    # configuring the endpoint is best placed to judge and tune at runtime.
    ai_review_concurrency: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
