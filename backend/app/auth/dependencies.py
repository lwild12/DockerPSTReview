import uuid
from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.users import current_active_user
from app.db import get_db
from app.models.case import CaseMembership, CaseRole
from app.models.user import User


def require_case_role(*allowed_roles: CaseRole) -> Callable:
    async def dependency(
        case_id: uuid.UUID,
        user: User = Depends(current_active_user),
        db: AsyncSession = Depends(get_db),
    ) -> CaseMembership:
        result = await db.execute(
            select(CaseMembership).where(
                CaseMembership.case_id == case_id, CaseMembership.user_id == user.id
            )
        )
        membership = result.scalar_one_or_none()
        if membership is None or (allowed_roles and membership.role not in allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not a member of this case with sufficient permissions",
            )
        return membership

    return dependency


require_case_member = require_case_role()
require_case_admin = require_case_role(CaseRole.admin)
require_case_reviewer_or_admin = require_case_role(CaseRole.admin, CaseRole.reviewer)
