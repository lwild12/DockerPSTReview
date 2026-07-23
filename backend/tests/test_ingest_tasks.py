import uuid

from app.models.case import Case, CaseMembership, CaseRole, Custodian
from app.models.document import DedupStatus, DocType, Document
from app.models.importjob import ImportStatus, PSTImportJob
from app.models.user import User
from app.services import pst_extraction
from app.services.pst_extraction import ExtractionResult, ManifestEntry
from app.tasks.ingest_tasks import run_import_job


async def _make_case_and_job(db_session, tmp_path):
    user = User(id=uuid.uuid4(), email=f"{uuid.uuid4()}@x.com", hashed_password="x", full_name="")
    db_session.add(user)
    await db_session.flush()

    case = Case(id=uuid.uuid4(), name="Test case", description="", created_by_id=user.id)
    db_session.add(case)
    custodian = Custodian(id=uuid.uuid4(), case_id=case.id, name="John Smith", email="")
    db_session.add(custodian)
    membership = CaseMembership(
        id=uuid.uuid4(), case_id=case.id, user_id=user.id, role=CaseRole.admin
    )
    db_session.add(membership)
    await db_session.flush()

    job = PSTImportJob(
        id=uuid.uuid4(),
        case_id=case.id,
        custodian_id=custodian.id,
        uploaded_filename="sample.pst",
        storage_path=str(tmp_path / "sample.pst"),
        created_by_id=user.id,
    )
    db_session.add(job)
    await db_session.commit()
    return case, job


def _write_eml(tmp_path, name: str, content: bytes) -> str:
    path = tmp_path / name
    path.write_bytes(content)
    return str(path)


async def test_full_pipeline_creates_documents_and_stats(db_session, tmp_path, monkeypatch):
    case, job = await _make_case_and_job(db_session, tmp_path)

    email_1 = _write_eml(
        tmp_path,
        "1.eml",
        b"From: alice@x.com\nTo: bob@x.com\nSubject: Hi\nMessage-ID: <m1@x.com>\n\nHello Bob\n",
    )
    email_2 = _write_eml(
        tmp_path,
        "2.eml",
        (
            b"From: bob@x.com\nTo: alice@x.com\nSubject: Re: Hi\n"
            b"Message-ID: <m2@x.com>\nIn-Reply-To: <m1@x.com>\nReferences: <m1@x.com>\n\n"
            b"Hi Alice\n"
        ),
    )
    # exact duplicate of email_1's content, to exercise dedup
    email_1_dup = _write_eml(
        tmp_path,
        "1-dup.eml",
        b"From: alice@x.com\nTo: bob@x.com\nSubject: Hi\nMessage-ID: <m1dup@x.com>\n\nHello Bob\n",
    )

    fake_result = ExtractionResult(
        entries=[
            ManifestEntry(id="e1", doc_type="email", staged_path=email_1, folder_path="Inbox"),
            ManifestEntry(id="e2", doc_type="email", staged_path=email_2, folder_path="Inbox"),
            ManifestEntry(id="e3", doc_type="email", staged_path=email_1_dup, folder_path="Sent"),
        ],
        fallback_used=False,
    )
    monkeypatch.setattr(pst_extraction, "extract_pst", lambda pst_path, staging: fake_result)

    await run_import_job(job.id, db_session)

    refreshed = await db_session.get(PSTImportJob, job.id)
    assert refreshed.status == ImportStatus.completed
    assert refreshed.stats["total_items"] == 3
    assert refreshed.stats["emails"] == 3
    assert refreshed.stats["duplicates"] == 1
    assert refreshed.stats["parse_errors"] == 0

    from sqlalchemy import select

    result = await db_session.execute(select(Document).where(Document.case_id == case.id))
    documents = {d.message_id: d for d in result.scalars().all()}

    assert documents["<m1@x.com>"].dedup_status == DedupStatus.primary
    assert documents["<m1dup@x.com>"].dedup_status == DedupStatus.duplicate
    assert documents["<m1dup@x.com>"].duplicate_of_id == documents["<m1@x.com>"].id

    # m1 and m2 form a reply chain and should share a thread; the duplicate does not reply to anyone
    assert documents["<m1@x.com>"].thread_id is not None
    assert documents["<m1@x.com>"].thread_id == documents["<m2@x.com>"].thread_id
    assert documents["<m1dup@x.com>"].thread_id is None

    # primary documents get rendered to a real PDF; the duplicate is skipped by design
    for msg_id in ("<m1@x.com>", "<m2@x.com>"):
        doc = documents[msg_id]
        assert doc.rendered_pdf_path, f"{msg_id} should have been rendered"
        assert doc.rendered_pdf_page_count > 0
        assert doc.render_error == ""
    assert documents["<m1dup@x.com>"].rendered_pdf_path == ""


async def test_pipeline_marks_job_failed_when_extraction_raises(db_session, tmp_path, monkeypatch):
    _, job = await _make_case_and_job(db_session, tmp_path)

    def _boom(pst_path, staging):
        raise pst_extraction.PSTExtractionError("no items could be extracted")

    monkeypatch.setattr(pst_extraction, "extract_pst", _boom)

    await run_import_job(job.id, db_session)

    refreshed = await db_session.get(PSTImportJob, job.id)
    assert refreshed.status == ImportStatus.failed
    assert "no items could be extracted" in refreshed.error_message


async def test_pipeline_stages_contact_and_calendar_entries(db_session, tmp_path, monkeypatch):
    case, job = await _make_case_and_job(db_session, tmp_path)

    vcard_path = tmp_path / "contact.vcf"
    vcard_path.write_text("BEGIN:VCARD\nVERSION:2.1\nFN:Jane Doe\nEMAIL:jane@x.com\nEND:VCARD\n")
    calendar_path = tmp_path / "cal.json"
    calendar_path.write_text('{"subject": "Quarterly review"}')

    fake_result = ExtractionResult(
        entries=[
            ManifestEntry(
                id="c1", doc_type="contact", staged_path=str(vcard_path), folder_path="Contacts"
            ),
            ManifestEntry(
                id="a1", doc_type="calendar", staged_path=str(calendar_path), folder_path="Calendar"
            ),
        ],
        fallback_used=True,
    )
    monkeypatch.setattr(pst_extraction, "extract_pst", lambda pst_path, staging: fake_result)

    await run_import_job(job.id, db_session)

    refreshed = await db_session.get(PSTImportJob, job.id)
    assert refreshed.status == ImportStatus.completed
    assert refreshed.stats["contacts"] == 1
    assert refreshed.stats["calendar_items"] == 1
    assert refreshed.stats["fallback_used"] is True

    from sqlalchemy import select

    result = await db_session.execute(select(Document).where(Document.case_id == case.id))
    by_type = {d.doc_type: d for d in result.scalars().all()}
    assert by_type[DocType.contact].subject == "Jane Doe"
    assert by_type[DocType.contact].structured_metadata["emails"] == ["jane@x.com"]
    assert by_type[DocType.calendar].subject == "Quarterly review"
