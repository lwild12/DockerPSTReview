import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import TimestampMixin, UUIDPKMixin


class ExportType(str, enum.Enum):
    production_set = "production_set"
    combined_pdf = "combined_pdf"


class ExportStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class ExportJob(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "export_jobs"

    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE")
    )
    review_set_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("review_sets.id"), nullable=True
    )
    export_type: Mapped[ExportType] = mapped_column(Enum(ExportType, name="export_type"))
    apply_bates: Mapped[bool] = mapped_column(Boolean, default=False)
    bates_prefix: Mapped[str] = mapped_column(String(50), default="")
    bates_start_number: Mapped[int] = mapped_column(Integer, default=1)
    bates_digit_padding: Mapped[int] = mapped_column(Integer, default=6)
    document_ids: Mapped[list] = mapped_column(JSONB, default=list)
    status: Mapped[ExportStatus] = mapped_column(
        Enum(ExportStatus, name="export_status"), default=ExportStatus.pending
    )
    celery_task_id: Mapped[str] = mapped_column(String(255), default="")
    output_storage_path: Mapped[str] = mapped_column(String(1000), default="")
    requested_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str] = mapped_column(Text, default="")


class ExportDocumentBates(UUIDPKMixin, Base):
    __tablename__ = "export_document_bates"

    export_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("export_jobs.id", ondelete="CASCADE")
    )
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"))
    bates_start: Mapped[str] = mapped_column(String(100), default="")
    bates_end: Mapped[str] = mapped_column(String(100), default="")
    page_count: Mapped[int] = mapped_column(Integer, default=0)
