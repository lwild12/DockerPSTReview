import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import TimestampMixin, UUIDPKMixin


class CodingFieldType(str, enum.Enum):
    single_select = "single_select"
    multi_select = "multi_select"


class CodingField(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "coding_fields"
    __table_args__ = (UniqueConstraint("case_id", "name", name="uq_case_coding_field_name"),)

    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(255))
    field_type: Mapped[CodingFieldType] = mapped_column(
        Enum(CodingFieldType, name="coding_field_type")
    )
    options: Mapped[list] = mapped_column(JSONB, default=list)
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))


class DocumentCodingValue(UUIDPKMixin, Base):
    __tablename__ = "document_coding_values"
    __table_args__ = (
        UniqueConstraint(
            "document_id", "coding_field_id", "value", name="uq_document_coding_value"
        ),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE")
    )
    coding_field_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("coding_fields.id", ondelete="CASCADE")
    )
    value: Mapped[str] = mapped_column(String(500))
    set_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    set_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
