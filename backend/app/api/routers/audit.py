import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_case_admin
from app.db import get_db
from app.models.audit import AuditLog
from app.models.case import CaseMembership
from app.schemas.audit import AuditLogRead

router = APIRouter(prefix="/cases/{case_id}/audit-logs", tags=["audit-logs"])


@router.get("", response_model=list[AuditLogRead])
async def list_audit_logs(
    case_id: uuid.UUID,
    page: int = 1,
    page_size: int = 50,
    _membership: CaseMembership = Depends(require_case_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.case_id == case_id)
        .order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return result.scalars().all()
