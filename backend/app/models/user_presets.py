import uuid

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import TimestampMixin, UUIDPKMixin


class UserTagPreset(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "user_tag_presets"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_user_tag_preset_name"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(255))
    color: Mapped[str] = mapped_column(String(20), default="#6366f1")


class UserRedactionReasonPreset(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "user_redaction_reason_presets"
    __table_args__ = (
        UniqueConstraint("user_id", "reason", name="uq_user_redaction_reason_preset"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    reason: Mapped[str] = mapped_column(Text)
