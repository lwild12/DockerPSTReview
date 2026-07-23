import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


def record_audit(
    db: AsyncSession,
    case_id: uuid.UUID,
    user_id: uuid.UUID | None,
    action: str,
    target_type: str = "",
    target_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditLog(
            id=uuid.uuid4(),
            case_id=case_id,
            user_id=user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            audit_metadata=metadata or {},
        )
    )
