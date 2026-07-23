import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_case_admin, require_case_member
from app.auth.users import current_active_user
from app.db import get_db
from app.models.case import CaseMembership
from app.models.importjob import PSTImportJob
from app.models.user import User
from app.schemas.importjob import ImportJobRead
from app.services import storage
from app.tasks.ingest_tasks import run_import_job_task

router = APIRouter(prefix="/cases/{case_id}/import-jobs", tags=["import-jobs"])


@router.get("", response_model=list[ImportJobRead])
async def list_import_jobs(
    case_id: uuid.UUID,
    _membership: CaseMembership = Depends(require_case_member),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PSTImportJob)
        .where(PSTImportJob.case_id == case_id)
        .order_by(PSTImportJob.created_at.desc())
    )
    return result.scalars().all()


@router.post("", response_model=ImportJobRead, status_code=status.HTTP_201_CREATED)
async def create_import_job(
    case_id: uuid.UUID,
    custodian_id: uuid.UUID = Form(...),
    file: UploadFile = File(...),
    _membership: CaseMembership = Depends(require_case_admin),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename or not file.filename.lower().endswith(".pst"):
        raise HTTPException(status_code=400, detail="Only .pst files are accepted")

    content = await file.read()
    job = PSTImportJob(
        id=uuid.uuid4(),
        case_id=case_id,
        custodian_id=custodian_id,
        uploaded_filename=file.filename,
        storage_path="",
        created_by_id=user.id,
    )
    job.storage_path = storage.save_upload(case_id, job.id, file.filename, content)
    db.add(job)
    await db.commit()
    await db.refresh(job)

    run_import_job_task.delay(str(job.id))

    return job


@router.get("/{import_job_id}", response_model=ImportJobRead)
async def get_import_job(
    case_id: uuid.UUID,
    import_job_id: uuid.UUID,
    _membership: CaseMembership = Depends(require_case_member),
    db: AsyncSession = Depends(get_db),
):
    job = await db.get(PSTImportJob, import_job_id)
    if job is None or job.case_id != case_id:
        raise HTTPException(status_code=404, detail="Import job not found")
    return job
