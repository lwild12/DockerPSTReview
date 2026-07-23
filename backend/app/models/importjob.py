import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import TimestampMixin, UUIDPKMixin


class ImportStatus(str, enum.Enum):
    pending = "pending"
    extracting = "extracting"
    parsing = "parsing"
    dedup = "dedup"
    rendering = "rendering"
    completed = "completed"
    completed_with_errors = "completed_with_errors"
    failed = "failed"


class PSTImportJob(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "pst_import_jobs"

    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE")
    )
    custodian_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("custodians.id"))
    uploaded_filename: Mapped[str] = mapped_column(String(500))
    storage_path: Mapped[str] = mapped_column(String(1000))
    status: Mapped[ImportStatus] = mapped_column(
        Enum(ImportStatus, name="import_status"), default=ImportStatus.pending
    )
    error_message: Mapped[str] = mapped_column(Text, default="")
    celery_task_id: Mapped[str] = mapped_column(String(255), default="")
    stats: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
