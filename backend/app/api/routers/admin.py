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
from app.services.encryption import encrypt

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


def _to_settings_read(row: SystemSettings) -> SystemSettingsRead:
    return SystemSettingsRead(
        enable_api_docs=row.enable_api_docs,
        cookie_secure=row.cookie_secure,
        oidc_enabled=row.oidc_enabled,
        oidc_issuer_url=row.oidc_issuer_url,
        oidc_client_id=row.oidc_client_id,
        oidc_client_secret_set=bool(row.oidc_client_secret_encrypted),
        oidc_display_name=row.oidc_display_name,
        updated_at=row.updated_at,
        updated_by_id=row.updated_by_id,
    )


@router.get("/settings", response_model=SystemSettingsRead)
async def get_system_settings(
    _superuser: User = Depends(current_superuser),
    db: AsyncSession = Depends(get_db),
):
    return _to_settings_read(await get_or_create_system_settings(db))


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
    if payload.oidc_issuer_url is not None:
        row.oidc_issuer_url = payload.oidc_issuer_url
    if payload.oidc_client_id is not None:
        row.oidc_client_id = payload.oidc_client_id
    if payload.oidc_display_name is not None:
        row.oidc_display_name = payload.oidc_display_name
    if payload.oidc_client_secret is not None:
        row.oidc_client_secret_encrypted = (
            encrypt(payload.oidc_client_secret) if payload.oidc_client_secret else ""
        )
    if payload.oidc_enabled is not None:
        if payload.oidc_enabled and not (
            row.oidc_issuer_url and row.oidc_client_id and row.oidc_client_secret_encrypted
        ):
            raise HTTPException(
                status_code=400,
                detail="Set an issuer URL, client ID, and client secret before enabling OIDC",
            )
        row.oidc_enabled = payload.oidc_enabled

    row.updated_by_id = current.id
    await db.commit()
    await db.refresh(row)
    return _to_settings_read(row)
