import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_case_admin, require_case_member
from app.auth.users import current_active_user
from app.db import get_db
from app.models.case import CaseMembership
from app.models.document import DedupStatus, Document
from app.models.importjob import PSTImportJob
from app.models.user import User
from app.schemas.importjob import ImportJobRead
from app.services import storage
from app.services.audit import record_audit
from app.tasks.ingest_tasks import run_import_job_task

router = APIRouter(prefix="/cases/{case_id}/import-jobs", tags=["import-jobs"])


async def _document_progress(import_job_id: uuid.UUID, db: AsyncSession) -> tuple[int, int, int]:
    """Counts scoped to this job's primary documents (the only ones ever
    rendered -- duplicates reuse their primary's rendered PDF at export
    time), so the fraction can actually reach 100% once rendering finishes."""
    base = (
        select(func.count())
        .select_from(Document)
        .where(
            Document.import_job_id == import_job_id, Document.dedup_status == DedupStatus.primary
        )
    )
    total = await db.scalar(base) or 0
    rendered = await db.scalar(base.where(Document.rendered_pdf_page_count > 0)) or 0
    failed = await db.scalar(base.where(Document.render_error != "")) or 0
    return total, rendered, failed


async def _to_read(job: PSTImportJob, db: AsyncSession) -> ImportJobRead:
    total, rendered, failed = await _document_progress(job.id, db)
    return ImportJobRead(
        **{c.name: getattr(job, c.name) for c in PSTImportJob.__table__.columns},
        documents_total=total,
        documents_rendered=rendered,
        documents_render_failed=failed,
    )


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
    jobs = result.scalars().all()
    return [await _to_read(job, db) for job in jobs]


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
    record_audit(
        db,
        case_id,
        user.id,
        "import_job.created",
        "pst_import_job",
        str(job.id),
        {"filename": file.filename, "custodian_id": str(custodian_id)},
    )
    await db.commit()
    await db.refresh(job)

    run_import_job_task.delay(str(job.id))

    return await _to_read(job, db)


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
    return await _to_read(job, db)
