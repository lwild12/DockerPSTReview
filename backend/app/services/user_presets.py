import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_presets import UserRedactionReasonPreset, UserTagPreset


async def upsert_tag_preset(db: AsyncSession, user_id: uuid.UUID, name: str, color: str) -> None:
    name = name.strip()
    if not name:
        return
    result = await db.execute(
        select(UserTagPreset).where(UserTagPreset.user_id == user_id, UserTagPreset.name == name)
    )
    preset = result.scalar_one_or_none()
    if preset is None:
        db.add(UserTagPreset(id=uuid.uuid4(), user_id=user_id, name=name, color=color))
    elif preset.color != color:
        preset.color = color


async def upsert_redaction_reason_preset(db: AsyncSession, user_id: uuid.UUID, reason: str) -> None:
    reason = reason.strip()
    if not reason:
        return
    result = await db.execute(
        select(UserRedactionReasonPreset).where(
            UserRedactionReasonPreset.user_id == user_id,
            UserRedactionReasonPreset.reason == reason,
        )
    )
    if result.scalar_one_or_none() is None:
        db.add(UserRedactionReasonPreset(id=uuid.uuid4(), user_id=user_id, reason=reason))
