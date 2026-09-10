import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin, UUIDPKMixin


class AiRelevanceStatus(enum.StrEnum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class DocumentAiRelevance(UUIDPKMixin, TimestampMixin, Base):
    """One row per document, overwritten in place on re-run -- no score
    history is kept, matching the wholesale-recompute pattern review
    analytics already uses."""

    __tablename__ = "document_ai_relevance"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), unique=True
    )
    status: Mapped[AiRelevanceStatus] = mapped_column(
        Enum(AiRelevanceStatus, name="ai_relevance_status"), default=AiRelevanceStatus.queued
    )
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rationale: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str] = mapped_column(Text, default="")
    model_name: Mapped[str] = mapped_column(String(255), default="")
    # The case's ai_review_criteria text at the time this document was
    # scored, so the UI can flag a score as stale if the criteria has since
    # changed, without needing a versioned score-history table.
    criteria_snapshot: Mapped[str] = mapped_column(Text, default="")
    scored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    document: Mapped["Document"] = relationship(back_populates="ai_relevance")  # noqa: F821
