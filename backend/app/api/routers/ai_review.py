import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    require_case_admin,
    require_case_member,
    require_case_reviewer_or_admin,
)
from app.db import get_db
from app.models.ai_review import AiRelevanceStatus, DocumentAiRelevance
from app.models.case import Case, CaseMembership
from app.models.document import Document
from app.models.system_settings import SystemSettings
from app.schemas.ai_review import AiReviewCriteriaUpdate, AiReviewRunRequest, AiReviewSummary
from app.schemas.document import DocumentAiRelevanceRead
from app.services.encryption import decrypt
from app.services.review_candidates import get_review_candidate_document_ids
from app.tasks.ai_review_tasks import _score_one_document, run_ai_review_task

router = APIRouter(prefix="/cases/{case_id}/ai-review", tags=["ai-review"])


async def _summary(case: Case, db: AsyncSession) -> AiReviewSummary:
    candidate_ids = await get_review_candidate_document_ids(case.id, db)

    system_settings = (await db.execute(select(SystemSettings).limit(1))).scalar_one_or_none()
    ollama_configured = bool(
        system_settings and system_settings.ollama_base_url and system_settings.ollama_model
    )

    status_counts = {status: 0 for status in AiRelevanceStatus}
    if candidate_ids:
        result = await db.execute(
            select(DocumentAiRelevance.status, func.count())
            .where(DocumentAiRelevance.document_id.in_(candidate_ids))
            .group_by(DocumentAiRelevance.status)
        )
        for status, count in result.all():
            status_counts[status] = count

    scored_count = sum(status_counts.values())
    return AiReviewSummary(
        criteria=case.ai_review_criteria,
        ollama_configured=ollama_configured,
        last_run_started_at=case.ai_review_last_run_started_at,
        last_run_completed_at=case.ai_review_last_run_completed_at,
        candidate_count=len(candidate_ids),
        unscored_count=len(candidate_ids) - scored_count,
        queued_count=status_counts[AiRelevanceStatus.queued],
        running_count=status_counts[AiRelevanceStatus.running],
        completed_count=status_counts[AiRelevanceStatus.completed],
        failed_count=status_counts[AiRelevanceStatus.failed],
    )


async def _get_case_or_404(case_id: uuid.UUID, db: AsyncSession) -> Case:
    case = await db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


async def _get_configured_system_settings_or_400(db: AsyncSession) -> SystemSettings:
    system_settings = (await db.execute(select(SystemSettings).limit(1))).scalar_one_or_none()
    if (
        not system_settings
        or not system_settings.ollama_base_url
        or not system_settings.ollama_model
    ):
        raise HTTPException(
            status_code=400,
            detail="Ollama is not configured -- set the endpoint URL and model in Admin settings",
        )
    return system_settings


@router.get("", response_model=AiReviewSummary)
async def get_ai_review_summary(
    case_id: uuid.UUID,
    _membership: CaseMembership = Depends(require_case_member),
    db: AsyncSession = Depends(get_db),
):
    case = await _get_case_or_404(case_id, db)
    return await _summary(case, db)


@router.patch("/criteria", response_model=AiReviewSummary)
async def update_ai_review_criteria(
    case_id: uuid.UUID,
    payload: AiReviewCriteriaUpdate,
    _membership: CaseMembership = Depends(require_case_reviewer_or_admin),
    db: AsyncSession = Depends(get_db),
):
    case = await _get_case_or_404(case_id, db)
    case.ai_review_criteria = payload.criteria
    await db.commit()
    await db.refresh(case)
    return await _summary(case, db)


@router.post("/run", response_model=AiReviewSummary)
async def run_ai_review(
    case_id: uuid.UUID,
    payload: AiReviewRunRequest,
    _membership: CaseMembership = Depends(require_case_admin),
    db: AsyncSession = Depends(get_db),
):
    case = await _get_case_or_404(case_id, db)
    await _get_configured_system_settings_or_400(db)

    run_ai_review_task.delay(str(case_id), rescore_all=payload.rescore_all)
    return await _summary(case, db)


@router.post("/documents/{document_id}/run", response_model=DocumentAiRelevanceRead)
async def run_ai_review_for_document(
    case_id: uuid.UUID,
    document_id: uuid.UUID,
    _membership: CaseMembership = Depends(require_case_admin),
    db: AsyncSession = Depends(get_db),
):
    """Score a single document immediately, synchronously (not dispatched
    to Celery) -- for an admin testing the case's criteria or the Ollama
    setup against one document at a time, rather than kicking off a full
    case run for every iteration."""
    case = await _get_case_or_404(case_id, db)
    document = await db.get(Document, document_id)
    if document is None or document.case_id != case_id:
        raise HTTPException(status_code=404, detail="Document not found")

    system_settings = await _get_configured_system_settings_or_400(db)
    api_key = (
        decrypt(system_settings.ollama_api_key_encrypted)
        if system_settings.ollama_api_key_encrypted
        else ""
    )

    await _score_one_document(
        document_id,
        criteria=case.ai_review_criteria,
        criteria_snapshot=case.ai_review_criteria,
        base_url=system_settings.ollama_base_url,
        model=system_settings.ollama_model,
        api_key=api_key,
        db=db,
    )
    await db.refresh(document, attribute_names=["ai_relevance"])
    return DocumentAiRelevanceRead.model_validate(document.ai_relevance)
