import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_case_admin, require_case_member
from app.auth.users import current_active_user
from app.db import get_db
from app.models.case import CaseMembership
from app.models.document import Document
from app.models.export import ExportJob, ExportStatus
from app.models.review import ReviewSet, ReviewSetDocument
from app.models.user import User
from app.schemas.export import ExportJobCreate, ExportJobRead
from app.tasks.export_tasks import run_export_task

router = APIRouter(prefix="/cases/{case_id}/export-jobs", tags=["export-jobs"])


@router.get("", response_model=list[ExportJobRead])
async def list_export_jobs(
    case_id: uuid.UUID,
    _membership: CaseMembership = Depends(require_case_member),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ExportJob).where(ExportJob.case_id == case_id).order_by(ExportJob.created_at.desc())
    )
    return result.scalars().all()


@router.post("", response_model=ExportJobRead, status_code=status.HTTP_201_CREATED)
async def create_export_job(
    case_id: uuid.UUID,
    payload: ExportJobCreate,
    _membership: CaseMembership = Depends(require_case_admin),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if payload.review_set_id is not None:
        review_set = await db.get(ReviewSet, payload.review_set_id)
        if review_set is None or review_set.case_id != case_id:
            raise HTTPException(status_code=404, detail="Review set not found")
        result = await db.execute(
            select(Document)
            .join(ReviewSetDocument, ReviewSetDocument.document_id == Document.id)
            .where(ReviewSetDocument.review_set_id == payload.review_set_id)
            .order_by(Document.sent_at.asc().nullslast())
        )
        document_ids = [d.id for d in result.scalars().all()]
    else:
        result = await db.execute(
            select(Document)
            .where(Document.id.in_(payload.document_ids), Document.case_id == case_id)
            .order_by(Document.sent_at.asc().nullslast())
        )
        document_ids = [d.id for d in result.scalars().all()]

    if not document_ids:
        raise HTTPException(status_code=400, detail="No documents resolved for this export")

    job = ExportJob(
        id=uuid.uuid4(),
        case_id=case_id,
        review_set_id=payload.review_set_id,
        export_type=payload.export_type,
        apply_bates=payload.apply_bates,
        bates_prefix=payload.bates_prefix,
        bates_start_number=payload.bates_start_number,
        bates_digit_padding=payload.bates_digit_padding,
        document_ids=[str(d) for d in document_ids],
        requested_by_id=user.id,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    run_export_task.delay(str(job.id))

    return job


@router.get("/{export_job_id}", response_model=ExportJobRead)
async def get_export_job(
    case_id: uuid.UUID,
    export_job_id: uuid.UUID,
    _membership: CaseMembership = Depends(require_case_member),
    db: AsyncSession = Depends(get_db),
):
    job = await db.get(ExportJob, export_job_id)
    if job is None or job.case_id != case_id:
        raise HTTPException(status_code=404, detail="Export job not found")
    return job


@router.get("/{export_job_id}/download")
async def download_export_job(
    case_id: uuid.UUID,
    export_job_id: uuid.UUID,
    _membership: CaseMembership = Depends(require_case_member),
    db: AsyncSession = Depends(get_db),
):
    job = await db.get(ExportJob, export_job_id)
    if job is None or job.case_id != case_id:
        raise HTTPException(status_code=404, detail="Export job not found")
    if job.status != ExportStatus.completed or not job.output_storage_path:
        raise HTTPException(status_code=409, detail="Export is not ready for download yet")
    media_type = (
        "application/zip" if job.output_storage_path.endswith(".zip") else "application/pdf"
    )
    filename = job.output_storage_path.rsplit("/", 1)[-1]
    return FileResponse(job.output_storage_path, media_type=media_type, filename=filename)
