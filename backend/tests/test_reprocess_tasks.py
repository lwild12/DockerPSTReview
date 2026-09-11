import uuid

from sqlalchemy import select

from app.models.ai_review import AiRelevanceStatus, DocumentAiRelevance
from app.models.case import Case, CaseMembership, CaseRole, Custodian
from app.models.document import DocType, Document
from app.models.importjob import ImportStatus, PSTImportJob
from app.models.tag import DocumentTag, Tag
from app.models.user import User
from app.services import pst_extraction
from app.services.pst_extraction import ExtractionResult, ManifestEntry
from app.tasks.reprocess_tasks import reprocess_case, reprocess_import_job


async def _make_case_and_job(
    db_session, tmp_path, *, fallback_used=False
) -> tuple[Case, PSTImportJob]:
    user = User(id=uuid.uuid4(), email=f"{uuid.uuid4()}@x.com", hashed_password="x", full_name="")
    db_session.add(user)
    await db_session.flush()

    case = Case(id=uuid.uuid4(), name="Reprocess case", description="", created_by_id=user.id)
    db_session.add(case)
    custodian = Custodian(id=uuid.uuid4(), case_id=case.id, name="John Smith", email="")
    db_session.add(custodian)
    db_session.add(
        CaseMembership(id=uuid.uuid4(), case_id=case.id, user_id=user.id, role=CaseRole.admin)
    )
    await db_session.flush()

    pst_path = tmp_path / "sample.pst"
    pst_path.write_bytes(b"not a real pst, just needs to exist on disk")
    job = PSTImportJob(
        id=uuid.uuid4(),
        case_id=case.id,
        custodian_id=custodian.id,
        uploaded_filename="sample.pst",
        storage_path=str(pst_path),
        created_by_id=user.id,
        status=ImportStatus.completed,
        stats={"fallback_used": fallback_used},
    )
    db_session.add(job)
    await db_session.commit()
    return case, job


def _write_eml(tmp_path, name: str, content: bytes) -> str:
    path = tmp_path / name
    path.write_bytes(content)
    return str(path)


async def test_reprocess_updates_matched_email_in_place_and_flags_change(
    db_session, tmp_path, monkeypatch
):
    case, job = await _make_case_and_job(db_session, tmp_path)

    # A prior import produced this document with a blank body (the RTF/
    # HTML-fallback bug) -- reprocessing should recognize it as the same
    # PST item (matching source_item_key) and update it in place.
    document = Document(
        id=uuid.uuid4(),
        case_id=case.id,
        import_job_id=job.id,
        doc_type=DocType.email,
        source_item_key="pypff-msg:42",
        subject="Old subject",
        body_text="",
        content_hash="old-hash",
    )
    db_session.add(document)
    await db_session.commit()
    original_id = document.id

    eml = _write_eml(
        tmp_path,
        "1.eml",
        b"From: a@x.com\nTo: b@x.com\nSubject: New subject\nMessage-ID: <m1@x.com>\n\n"
        b"Recovered body text\n",
    )
    fake_result = ExtractionResult(
        entries=[
            ManifestEntry(
                id="e1",
                doc_type="email",
                staged_path=eml,
                folder_path="Inbox",
                source_item_key="pypff-msg:42",
            )
        ],
        fallback_used=False,
    )
    monkeypatch.setattr(pst_extraction, "extract_pst", lambda pst_path, staging: fake_result)

    stats = await reprocess_import_job(job, db_session)

    assert stats == {
        "total_items": 1,
        "new": 0,
        "updated": 1,
        "unchanged": 0,
        "orphans_deleted": 0,
        "orphans_kept": 0,
        "parse_errors": 0,
    }

    refreshed = await db_session.get(Document, original_id)
    assert refreshed is not None, "the same document row should have been updated, not replaced"
    assert refreshed.subject == "New subject"
    assert "Recovered body text" in refreshed.body_text
    assert refreshed.content_changed_at is not None


async def test_reprocess_leaves_unchanged_email_alone(db_session, tmp_path, monkeypatch):
    case, job = await _make_case_and_job(db_session, tmp_path)

    eml = _write_eml(
        tmp_path,
        "1.eml",
        b"From: a@x.com\nTo: b@x.com\nSubject: Same\nMessage-ID: <m1@x.com>\n\nSame body\n",
    )
    fake_result = ExtractionResult(
        entries=[
            ManifestEntry(
                id="e1",
                doc_type="email",
                staged_path=eml,
                folder_path="Inbox",
                source_item_key="pypff-msg:1",
            )
        ],
        fallback_used=False,
    )
    monkeypatch.setattr(pst_extraction, "extract_pst", lambda pst_path, staging: fake_result)

    # First pass: nothing exists yet, so this creates the document (and
    # its real content_hash).
    stats = await reprocess_import_job(job, db_session)
    assert stats["new"] == 1
    result = await db_session.execute(select(Document).where(Document.case_id == case.id))
    document = result.scalar_one()
    assert document.content_changed_at is None

    # Second pass against identical content should be a pure no-op.
    stats_again = await reprocess_import_job(job, db_session)
    assert stats_again == {
        "total_items": 1,
        "new": 0,
        "updated": 0,
        "unchanged": 1,
        "orphans_deleted": 0,
        "orphans_kept": 0,
        "parse_errors": 0,
    }
    refreshed = await db_session.get(Document, document.id)
    assert refreshed.content_changed_at is None


async def test_reprocess_deletes_untouched_orphan_attachment(db_session, tmp_path, monkeypatch):
    case, job = await _make_case_and_job(db_session, tmp_path)

    parent = Document(
        id=uuid.uuid4(),
        case_id=case.id,
        import_job_id=job.id,
        doc_type=DocType.email,
        source_item_key="pypff-msg:7",
        subject="Has an attachment",
        content_hash="parent-old-hash",
    )
    db_session.add(parent)
    await db_session.flush()
    orphan_attachment = Document(
        id=uuid.uuid4(),
        case_id=case.id,
        import_job_id=job.id,
        doc_type=DocType.attachment,
        parent_document_id=parent.id,
        subject="image007.png",
        content_hash="attachment-hash-not-seen-again",
    )
    db_session.add(orphan_attachment)
    await db_session.commit()
    orphan_id = orphan_attachment.id

    # Reprocessed: the image is now correctly recognized as inline (the
    # content-hash dedup fix), so this pass produces zero attachments for
    # this email at all.
    eml = _write_eml(
        tmp_path,
        "1.eml",
        b"From: a@x.com\nTo: b@x.com\nSubject: Has an attachment\nMessage-ID: <m1@x.com>\n\n"
        b"Body\n",
    )
    fake_result = ExtractionResult(
        entries=[
            ManifestEntry(
                id="e1",
                doc_type="email",
                staged_path=eml,
                folder_path="Inbox",
                source_item_key="pypff-msg:7",
            )
        ],
        fallback_used=False,
    )
    monkeypatch.setattr(pst_extraction, "extract_pst", lambda pst_path, staging: fake_result)

    stats = await reprocess_import_job(job, db_session)

    assert stats["orphans_deleted"] == 1
    assert stats["orphans_kept"] == 0
    assert await db_session.get(Document, orphan_id) is None


async def test_reprocess_keeps_orphan_attachment_with_review_work(
    db_session, tmp_path, monkeypatch
):
    case, job = await _make_case_and_job(db_session, tmp_path)
    user = (await db_session.execute(select(User))).scalars().first()

    parent = Document(
        id=uuid.uuid4(),
        case_id=case.id,
        import_job_id=job.id,
        doc_type=DocType.email,
        source_item_key="pypff-msg:8",
        subject="Has a tagged attachment",
        content_hash="parent-old-hash-2",
    )
    db_session.add(parent)
    await db_session.flush()
    tagged_attachment = Document(
        id=uuid.uuid4(),
        case_id=case.id,
        import_job_id=job.id,
        doc_type=DocType.attachment,
        parent_document_id=parent.id,
        subject="hot-doc.png",
        content_hash="attachment-hash-tagged",
    )
    db_session.add(tagged_attachment)
    await db_session.flush()
    tag = Tag(id=uuid.uuid4(), case_id=case.id, name="Hot doc", created_by_id=user.id)
    db_session.add(tag)
    await db_session.flush()
    db_session.add(
        DocumentTag(document_id=tagged_attachment.id, tag_id=tag.id, tagged_by_id=user.id)
    )
    await db_session.commit()
    tagged_id = tagged_attachment.id

    eml = _write_eml(
        tmp_path,
        "1.eml",
        b"From: a@x.com\nTo: b@x.com\nSubject: Has a tagged attachment\n"
        b"Message-ID: <m1@x.com>\n\nBody\n",
    )
    fake_result = ExtractionResult(
        entries=[
            ManifestEntry(
                id="e1",
                doc_type="email",
                staged_path=eml,
                folder_path="Inbox",
                source_item_key="pypff-msg:8",
            )
        ],
        fallback_used=False,
    )
    monkeypatch.setattr(pst_extraction, "extract_pst", lambda pst_path, staging: fake_result)

    stats = await reprocess_import_job(job, db_session)

    assert stats["orphans_deleted"] == 0
    assert stats["orphans_kept"] == 1
    assert await db_session.get(Document, tagged_id) is not None


async def test_reprocess_clears_ai_relevance_when_content_changes(
    db_session, tmp_path, monkeypatch
):
    case, job = await _make_case_and_job(db_session, tmp_path)

    document = Document(
        id=uuid.uuid4(),
        case_id=case.id,
        import_job_id=job.id,
        doc_type=DocType.email,
        source_item_key="pypff-msg:99",
        subject="Old",
        content_hash="stale-hash",
    )
    db_session.add(document)
    await db_session.flush()
    db_session.add(
        DocumentAiRelevance(
            document_id=document.id,
            status=AiRelevanceStatus.completed,
            score=5,
            rationale="scored against the old, incomplete content",
        )
    )
    await db_session.commit()

    eml = _write_eml(
        tmp_path,
        "1.eml",
        b"From: a@x.com\nTo: b@x.com\nSubject: New\nMessage-ID: <m1@x.com>\n\nNew body\n",
    )
    fake_result = ExtractionResult(
        entries=[
            ManifestEntry(
                id="e1",
                doc_type="email",
                staged_path=eml,
                folder_path="Inbox",
                source_item_key="pypff-msg:99",
            )
        ],
        fallback_used=False,
    )
    monkeypatch.setattr(pst_extraction, "extract_pst", lambda pst_path, staging: fake_result)

    await reprocess_import_job(job, db_session)

    result = await db_session.execute(
        select(DocumentAiRelevance).where(DocumentAiRelevance.document_id == document.id)
    )
    assert result.scalar_one_or_none() is None


async def test_reprocess_case_skips_fallback_imported_jobs(db_session, tmp_path, monkeypatch):
    case, job = await _make_case_and_job(db_session, tmp_path, fallback_used=True)

    called = False

    async def _fail_if_called(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr("app.tasks.reprocess_tasks.reprocess_import_job", _fail_if_called)

    summary = await reprocess_case(case.id, db_session)

    assert called is False
    assert len(summary["jobs"]) == 1
    assert summary["jobs"][0]["skipped"] is True
    assert "fallback" in summary["jobs"][0]["reason"]


async def test_reprocess_case_skips_job_whose_pst_is_missing(db_session, tmp_path):
    case, job = await _make_case_and_job(db_session, tmp_path)
    job.storage_path = str(tmp_path / "does-not-exist.pst")
    await db_session.commit()

    summary = await reprocess_case(case.id, db_session)

    assert len(summary["jobs"]) == 1
    assert summary["jobs"][0]["skipped"] is True
    assert "no longer on disk" in summary["jobs"][0]["reason"]


async def test_reprocess_case_tracks_progress(db_session, tmp_path):
    case, job = await _make_case_and_job(db_session, tmp_path, fallback_used=True)

    await reprocess_case(case.id, db_session)

    refreshed = await db_session.get(Case, case.id)
    assert refreshed.reprocess_progress == {
        "total_jobs": 1,
        "completed_jobs": 1,
        "current_job_id": None,
    }
