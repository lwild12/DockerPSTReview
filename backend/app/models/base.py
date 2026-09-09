import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


def orm_columns(obj: Any) -> dict[str, Any]:
    """A model instance's own table columns as a plain dict, for merging with
    computed extra fields before handing the result to a Pydantic schema's
    model_validate (e.g. `{**orm_columns(doc), "attachment_count": count}`)."""
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


class UUIDPKMixin:
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
