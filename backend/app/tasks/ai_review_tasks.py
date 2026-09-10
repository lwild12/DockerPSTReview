from __future__ import annotations

import asyncio
import html
import logging
import re
import uuid
from datetime import UTC, datetime

import nh3
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.celery_app import celery_app
from app.config import get_settings
from app.models.ai_review import AiRelevanceStatus, DocumentAiRelevance
from app.models.case import Case
from app.models.document import Document
from app.models.system_settings import SystemSettings
from app.services.encryption import decrypt
from app.services.ollama_client import OllamaError, score_document_relevance
from app.services.review_candidates import get_review_candidate_document_ids

logger = logging.getLogger(__name__)
settings = get_settings()

_BLOCK_BREAK_RE = re.compile(r"(?i)</(p|div|li|tr|h[1-6]|blockquote)>|<br\s*/?>")


def _plain_text_from_html(html_body: str) -> str:
    """Rough plain-text extraction for feeding an HTML-only email body to
    the LLM -- not for display. Many corporate/templated emails have no
    text/plain alternative part at all, only HTML, so body_text is empty
    for them even though real content exists in body_html. A newline is
    inserted where block-level tags close, before stripping every
    remaining tag (nh3 drops <script>/<style> content along with their
    tags, matching how a browser would render it) -- otherwise adjacent
    paragraphs run together with no separation at all."""
    with_breaks = _BLOCK_BREAK_RE.sub("\n", html_body)
    return html.unescape(nh3.clean(with_breaks, tags=set()))


def _text_for_scoring(document: Document) -> str:
    """Best available text content to send the model. body_text when
    present; otherwise a plain-text extraction from body_html for
    HTML-only emails. ocr_text (attachments OCR'd because their PDF had
    no extractable text layer) is appended too rather than substituted,
    since it's a genuinely separate source that's never wrong to include
    when present.

    body_text is checked for actual (non-whitespace) content, not just
    truthiness -- a real email observed in production had a `text/plain`
    part containing only "\n", a near-empty placeholder some mail clients
    generate alongside the real HTML-formatted content. That string is
    non-empty so a plain `if document.body_text:` took it and never fell
    back to body_html, sending the model 1 character of body text for a
    message with a full, substantial HTML body."""
    parts = []
    if document.body_text and document.body_text.strip():
        parts.append(document.body_text)
    elif document.body_html:
        parts.append(_plain_text_from_html(document.body_html))
    if document.ocr_text:
        parts.append(document.ocr_text)
    return "\n\n".join(parts)


async def _get_system_settings(db: AsyncSession) -> SystemSettings:
    result = await db.execute(select(SystemSettings).limit(1))
    row = result.scalar_one_or_none()
    if row is None:
        row = SystemSettings()
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return row


async def _score_one_document(
    document_id: uuid.UUID,
    *,
    criteria: str,
    criteria_snapshot: str,
    base_url: str,
    model: str,
    api_key: str,
    db: AsyncSession,
    log_requests: bool = False,
) -> None:
    document = await db.get(Document, document_id)
    if document is None:
        return

    result = await db.execute(
        select(DocumentAiRelevance).where(DocumentAiRelevance.document_id == document_id)
    )
    relevance = result.scalar_one_or_none()
    if relevance is None:
        relevance = DocumentAiRelevance(document_id=document_id, status=AiRelevanceStatus.queued)
        db.add(relevance)

    relevance.status = AiRelevanceStatus.running
    await db.commit()

    try:
        scored = await score_document_relevance(
            base_url=base_url,
            model=model,
            api_key=api_key,
            criteria=criteria,
            subject=document.subject,
            sender=document.sender,
            body=_text_for_scoring(document),
            log_requests=log_requests,
        )
    except OllamaError as exc:
        relevance.status = AiRelevanceStatus.failed
        relevance.error = str(exc)[:2000]
        await db.commit()
        return

    relevance.status = AiRelevanceStatus.completed
    relevance.score = scored.score
    relevance.rationale = scored.rationale
    relevance.error = ""
    relevance.model_name = model
    relevance.criteria_snapshot = criteria_snapshot
    relevance.scored_at = datetime.now(UTC)
    await db.commit()


async def run_ai_review(case_id: uuid.UUID, db: AsyncSession, *, rescore_all: bool = False) -> None:
    """Score every review-candidate document in a case against its
    ai_review_criteria. By default (rescore_all=False) only documents
    that have never been scored, previously failed, or were scored
    against a since-changed criteria string are (re)scored -- a
    completed score whose criteria_snapshot still matches the case's
    current criteria is left alone. rescore_all=True ignores that and
    rescores every candidate regardless of its current status."""
    case = await db.get(Case, case_id)
    if case is None:
        return

    system_settings = await _get_system_settings(db)
    criteria = case.ai_review_criteria
    concurrency = max(1, system_settings.ai_review_concurrency)

    api_key = (
        decrypt(system_settings.ollama_api_key_encrypted)
        if system_settings.ollama_api_key_encrypted
        else ""
    )

    case.ai_review_last_run_started_at = datetime.now(UTC)
    case.ai_review_last_run_completed_at = None
    await db.commit()

    try:
        document_ids = await get_review_candidate_document_ids(case_id, db)
        if not rescore_all:
            existing = await db.execute(
                select(
                    DocumentAiRelevance.document_id,
                    DocumentAiRelevance.status,
                    DocumentAiRelevance.criteria_snapshot,
                ).where(DocumentAiRelevance.document_id.in_(document_ids))
            )
            up_to_date = {
                row.document_id
                for row in existing
                if row.status == AiRelevanceStatus.completed and row.criteria_snapshot == criteria
            }
            document_ids = [d for d in document_ids if d not in up_to_date]

        if document_ids:
            session_maker = async_sessionmaker(db.bind, expire_on_commit=False)
            semaphore = asyncio.Semaphore(concurrency)

            async def _score_one(document_id: uuid.UUID) -> None:
                async with semaphore, session_maker() as session:
                    await _score_one_document(
                        document_id,
                        criteria=criteria,
                        criteria_snapshot=criteria,
                        base_url=system_settings.ollama_base_url,
                        model=system_settings.ollama_model,
                        api_key=api_key,
                        db=session,
                        log_requests=system_settings.ollama_log_requests,
                    )

            # return_exceptions=True: _score_one_document already catches its
            # own expected failure mode (OllamaError) and records it on the
            # document's relevance row -- an exception escaping here means
            # something unexpected (e.g. a DB error), and one such failure
            # shouldn't lose the results of every other document scoring
            # concurrently in this batch.
            results = await asyncio.gather(
                *(_score_one(document_id) for document_id in document_ids),
                return_exceptions=True,
            )
            for document_id, outcome in zip(document_ids, results, strict=True):
                if isinstance(outcome, BaseException):
                    logger.warning(
                        "Unexpected failure scoring document %s", document_id, exc_info=outcome
                    )
    finally:
        case.ai_review_last_run_completed_at = datetime.now(UTC)
        await db.commit()


async def _run_ai_review_standalone(case_id: uuid.UUID, *, rescore_all: bool) -> None:
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_maker() as db:
            await run_ai_review(case_id, db, rescore_all=rescore_all)
    finally:
        await engine.dispose()


@celery_app.task(name="ai_review.run_ai_review")
def run_ai_review_task(case_id: str, rescore_all: bool = False) -> None:
    asyncio.run(_run_ai_review_standalone(uuid.UUID(case_id), rescore_all=rescore_all))
