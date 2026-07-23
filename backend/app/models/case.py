import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin, UUIDPKMixin


class CaseRole(str, enum.Enum):
    admin = "admin"
    reviewer = "reviewer"
    viewer = "viewer"


class Case(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "cases"

    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(String(2000), default="")
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

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
