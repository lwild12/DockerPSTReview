import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_case_admin, require_case_member
from app.auth.users import current_active_user
from app.db import get_db
from app.models.case import Case, CaseMembership, CaseRole
from app.models.user import User
from app.schemas.case import CaseCreate, CaseMemberCreate, CaseMemberRead, CaseRead

router = APIRouter(prefix="/cases", tags=["cases"])


@router.get("", response_model=list[CaseRead])
async def list_cases(
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Case, CaseMembership.role)
        .join(CaseMembership, CaseMembership.case_id == Case.id)
        .where(CaseMembership.user_id == user.id)
        .order_by(Case.created_at.desc())
    )
    cases = []
    for case, role in result.all():
        item = CaseRead.model_validate(case)
        item.my_role = role
        cases.append(item)
    return cases


@router.post("", response_model=CaseRead, status_code=status.HTTP_201_CREATED)
async def create_case(
    payload: CaseCreate,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
):
    case = Case(name=payload.name, description=payload.description, created_by_id=user.id)
    db.add(case)
    await db.flush()
    membership = CaseMembership(case_id=case.id, user_id=user.id, role=CaseRole.admin)
    db.add(membership)
    await db.commit()
    await db.refresh(case)
    item = CaseRead.model_validate(case)
    item.my_role = CaseRole.admin
    return item


@router.get("/{case_id}", response_model=CaseRead)
async def get_case(
    case_id: uuid.UUID,
    membership: CaseMembership = Depends(require_case_member),
    db: AsyncSession = Depends(get_db),
):
    case = await db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    item = CaseRead.model_validate(case)
    item.my_role = membership.role
    return item


@router.get("/{case_id}/members", response_model=list[CaseMemberRead])
async def list_members(
    case_id: uuid.UUID,
    _membership: CaseMembership = Depends(require_case_member),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(CaseMembership).where(CaseMembership.case_id == case_id))
    return result.scalars().all()


@router.post(
    "/{case_id}/members", response_model=CaseMemberRead, status_code=status.HTTP_201_CREATED
)
async def add_member(
    case_id: uuid.UUID,
    payload: CaseMemberCreate,
    _membership: CaseMembership = Depends(require_case_admin),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(
        select(CaseMembership).where(
            CaseMembership.case_id == case_id, CaseMembership.user_id == payload.user_id
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="User is already a member of this case")
    membership = CaseMembership(case_id=case_id, user_id=payload.user_id, role=payload.role)
    db.add(membership)
    await db.commit()
    await db.refresh(membership)
    return membership


@router.delete("/{case_id}/members/{membership_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    case_id: uuid.UUID,
    membership_id: uuid.UUID,
    _membership: CaseMembership = Depends(require_case_admin),
    db: AsyncSession = Depends(get_db),
):
    target = await db.get(CaseMembership, membership_id)
    if target is None or target.case_id != case_id:
        raise HTTPException(status_code=404, detail="Membership not found")
    await db.delete(target)
    await db.commit()
