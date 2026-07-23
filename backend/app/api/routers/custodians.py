import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_case_admin, require_case_member
from app.db import get_db
from app.models.case import CaseMembership, Custodian
from app.schemas.case import CustodianCreate, CustodianRead

router = APIRouter(prefix="/cases/{case_id}/custodians", tags=["custodians"])


@router.get("", response_model=list[CustodianRead])
async def list_custodians(
    case_id: uuid.UUID,
    _membership: CaseMembership = Depends(require_case_member),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Custodian).where(Custodian.case_id == case_id))
    return result.scalars().all()


@router.post("", response_model=CustodianRead, status_code=status.HTTP_201_CREATED)
async def create_custodian(
    case_id: uuid.UUID,
    payload: CustodianCreate,
    _membership: CaseMembership = Depends(require_case_admin),
    db: AsyncSession = Depends(get_db),
):
    custodian = Custodian(case_id=case_id, name=payload.name, email=payload.email)
    db.add(custodian)
    await db.commit()
    await db.refresh(custodian)
    return custodian
