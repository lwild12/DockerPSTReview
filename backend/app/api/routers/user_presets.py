import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.users import current_active_user
from app.db import get_db
from app.models.user import User
from app.models.user_presets import UserRedactionReasonPreset, UserTagPreset
from app.schemas.user_presets import UserRedactionReasonPresetRead, UserTagPresetRead

router = APIRouter(prefix="/me", tags=["user-presets"])


@router.get("/tag-presets", response_model=list[UserTagPresetRead])
async def list_tag_presets(
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserTagPreset).where(UserTagPreset.user_id == user.id).order_by(UserTagPreset.name)
    )
    return result.scalars().all()


@router.delete("/tag-presets/{preset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag_preset(
    preset_id: uuid.UUID,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
):
    preset = await db.get(UserTagPreset, preset_id)
    if preset is None or preset.user_id != user.id:
        raise HTTPException(status_code=404, detail="Preset not found")
    await db.delete(preset)
    await db.commit()


@router.get("/redaction-reason-presets", response_model=list[UserRedactionReasonPresetRead])
async def list_redaction_reason_presets(
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserRedactionReasonPreset)
        .where(UserRedactionReasonPreset.user_id == user.id)
        .order_by(UserRedactionReasonPreset.reason)
    )
    return result.scalars().all()


@router.delete("/redaction-reason-presets/{preset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_redaction_reason_preset(
    preset_id: uuid.UUID,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
):
    preset = await db.get(UserRedactionReasonPreset, preset_id)
    if preset is None or preset.user_id != user.id:
        raise HTTPException(status_code=404, detail="Preset not found")
    await db.delete(preset)
    await db.commit()
