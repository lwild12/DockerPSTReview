import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.users import current_superuser
from app.config import get_settings
from app.db import get_db
from app.models.system_settings import SystemSettings
from app.models.user import User
from app.schemas.admin import (
    AdminUserRead,
    AdminUserUpdate,
    SystemSettingsRead,
    SystemSettingsUpdate,
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[AdminUserRead])
async def list_all_users(
    _superuser: User = Depends(current_superuser),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).order_by(User.email))
    return result.scalars().all()


@router.patch("/users/{user_id}", response_model=AdminUserRead)
async def update_user_admin_fields(
    user_id: uuid.UUID,
    payload: AdminUserUpdate,
    current: User = Depends(current_superuser),
    db: AsyncSession = Depends(get_db),
):
    target = await db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")

    if target.id == current.id and (payload.is_active is False or payload.is_superuser is False):
        raise HTTPException(
            status_code=400,
            detail="You cannot deactivate or remove your own superuser status",
        )

    if payload.is_active is not None:
        target.is_active = payload.is_active
    if payload.is_superuser is not None:
        target.is_superuser = payload.is_superuser
    await db.commit()
    await db.refresh(target)
    return target


async def get_or_create_system_settings(db: AsyncSession) -> SystemSettings:
    result = await db.execute(select(SystemSettings).limit(1))
    row = result.scalar_one_or_none()
    if row is None:
        env = get_settings()
        row = SystemSettings(
            id=uuid.uuid4(),
            enable_api_docs=env.enable_api_docs,
            cookie_secure=env.cookie_secure,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return row


@router.get("/settings", response_model=SystemSettingsRead)
async def get_system_settings(
    _superuser: User = Depends(current_superuser),
    db: AsyncSession = Depends(get_db),
):
    return await get_or_create_system_settings(db)


@router.patch("/settings", response_model=SystemSettingsRead)
async def update_system_settings(
    payload: SystemSettingsUpdate,
    current: User = Depends(current_superuser),
    db: AsyncSession = Depends(get_db),
):
    row = await get_or_create_system_settings(db)
    if payload.enable_api_docs is not None:
        row.enable_api_docs = payload.enable_api_docs
    if payload.cookie_secure is not None:
        row.cookie_secure = payload.cookie_secure
    row.updated_by_id = current.id
    await db.commit()
    await db.refresh(row)
    return row
