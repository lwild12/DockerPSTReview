import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin, UUIDPKMixin


class CaseRole(enum.StrEnum):
    admin = "admin"
    reviewer = "reviewer"
    viewer = "viewer"


class Case(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "cases"

    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(String(2000), default="")
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    analytics_computed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Free-text relevance criteria for AI pre-review -- deliberately separate
    # from `description` so editing the case description doesn't silently
    # change what an AI review run was scored against.
    ai_review_criteria: Mapped[str] = mapped_column(Text, default="")
    ai_review_last_run_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ai_review_last_run_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    memberships: Mapped[list["CaseMembership"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
    custodians: Mapped[list["Custodian"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )


class CaseMembership(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "case_memberships"
    __table_args__ = (UniqueConstraint("case_id", "user_id", name="uq_case_member"),)

    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    role: Mapped[CaseRole] = mapped_column(Enum(CaseRole, name="case_role"))

    case: Mapped["Case"] = relationship(back_populates="memberships")


class Custodian(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "custodians"

    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), default="")

    case: Mapped["Case"] = relationship(back_populates="custodians")
