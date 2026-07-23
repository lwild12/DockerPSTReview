import enum
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin, UUIDPKMixin


class DocType(str, enum.Enum):
    email = "email"
    attachment = "attachment"
    calendar = "calendar"
    contact = "contact"


class DedupStatus(str, enum.Enum):
    primary = "primary"
    duplicate = "duplicate"


class Thread(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "threads"

    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE")
    )
    root_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", use_alter=True, name="fk_threads_root_document_id"),
        nullable=True,
    )
    subject_normalized: Mapped[str] = mapped_column(String(500), default="")
    participant_hash: Mapped[str] = mapped_column(String(64), default="")


class Document(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "documents"

    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE")
    )
    import_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pst_import_jobs.id"), nullable=True
    )
    custodian_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("custodians.id"), nullable=True
    )
    doc_type: Mapped[DocType] = mapped_column(Enum(DocType, name="doc_type"))
    parent_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True
    )
    thread_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("threads.id"), nullable=True
    )

    subject: Mapped[str] = mapped_column(String(1000), default="")
    sender: Mapped[str] = mapped_column(String(500), default="")
    recipients_to: Mapped[list] = mapped_column(JSONB, default=list)
    recipients_cc: Mapped[list] = mapped_column(JSONB, default=list)
    recipients_bcc: Mapped[list] = mapped_column(JSONB, default=list)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    message_id: Mapped[str] = mapped_column(String(500), default="")
    in_reply_to: Mapped[str] = mapped_column(String(500), default="")
    references: Mapped[list] = mapped_column(JSONB, default=list)

    body_text: Mapped[str] = mapped_column(Text, default="")
    body_html: Mapped[str] = mapped_column(Text, default="")
    structured_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)

    pst_folder_path: Mapped[str] = mapped_column(String(1000), default="")
    native_file_path: Mapped[str] = mapped_column(String(1000), default="")
    mime_type: Mapped[str] = mapped_column(String(255), default="")
    file_size: Mapped[int] = mapped_column(BigInteger, default=0)

    rendered_pdf_path: Mapped[str] = mapped_column(String(1000), default="")
    rendered_pdf_page_count: Mapped[int] = mapped_column(Integer, default=0)
    render_error: Mapped[str] = mapped_column(Text, default="")

    content_hash: Mapped[str] = mapped_column(String(64), default="", index=True)
    dedup_status: Mapped[DedupStatus] = mapped_column(
        Enum(DedupStatus, name="dedup_status"), default=DedupStatus.primary
    )
    duplicate_of_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True
    )

    tags: Mapped[list["DocumentTag"]] = relationship(  # noqa: F821
        back_populates="document", cascade="all, delete-orphan"
    )
    redactions: Mapped[list["Redaction"]] = relationship(  # noqa: F821
        back_populates="document", cascade="all, delete-orphan"
    )
