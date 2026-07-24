from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.users import auth_backend, fastapi_users
from app.db import get_db
from app.models.system_settings import SystemSettings
from app.schemas.user import UserCreate, UserRead, UserUpdate

router = APIRouter(prefix="/auth", tags=["auth"])

router.include_router(fastapi_users.get_auth_router(auth_backend))
router.include_router(fastapi_users.get_register_router(UserRead, UserCreate))
router.include_router(fastapi_users.get_reset_password_router())
router.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
)


@router.get("/registration-enabled")
async def registration_enabled(db: AsyncSession = Depends(get_db)):
    """Unauthenticated -- lets the login/register pages know whether to
    show the registration link (the very first account can always still
    register, so this reflects the admin's toggle, not that bootstrap case)."""
    result = await db.execute(select(SystemSettings.registration_enabled).limit(1))
    row = result.scalar_one_or_none()
    return {"enabled": row if row is not None else True}
