import uuid
import zipfile

import fitz

from app.models.case import Case, CaseMembership, CaseRole, Custodian
from app.models.document import DocType, Document
from app.models.export import ExportJob, ExportStatus, ExportType
from app.models.redaction import Redaction
from app.models.user import User
from app.tasks.export_tasks import run_export


async def _make_case(db_session):
    user = User(id=uuid.uuid4(), email=f"{uuid.uuid4()}@x.com", hashed_password="x", full_name="")
    db_session.add(user)
    await db_session.flush()
    case = Case(id=uuid.uuid4(), name="Export case", description="", created_by_id=user.id)
    db_session.add(case)
    custodian = Custodian(id=uuid.uuid4(), case_id=case.id, name="John Smith", email="")
    db_session.add(custodian)
    db_session.add(
        CaseMembership(id=uuid.uuid4(), case_id=case.id, user_id=user.id, role=CaseRole.admin)
    )
    await db_session.flush()
    return user, case, custodian


def _write_pdf(tmp_path, name: str, text: str) -> str:
    doc = fitz.open()
    doc.new_page(width=612, height=792).insert_text((72, 72), text, fontsize=12)
    path = tmp_path / name
    doc.save(str(path))
    return str(path)


async def test_export_combined_pdf_burns_in_redactions_and_merges_in_order(db_session, tmp_path):
    user, case, custodian = await _make_case(db_session)

    doc1 = Document(
        id=uuid.uuid4(),
        case_id=case.id,
        custodian_id=custodian.id,
        doc_type=DocType.email,
        subject="First",
        content_hash=str(uuid.uuid4()),
        rendered_pdf_path=_write_pdf(tmp_path, "1.pdf", "First doc SSN 123-45-6789 confidential"),
        rendered_pdf_page_count=1,
    )
    doc2 = Document(
        id=uuid.uuid4(),
        case_id=case.id,
        custodian_id=custodian.id,
        doc_type=DocType.email,
        subject="Second",
        content_hash=str(uuid.uuid4()),
        rendered_pdf_path=_write_pdf(tmp_path, "2.pdf", "Second doc, nothing sensitive"),
        rendered_pdf_page_count=1,
    )
    db_session.add_all([doc1, doc2])
    await db_session.flush()

    # locate the SSN's real position so the redaction is meaningful, not just present
    with fitz.open(doc1.rendered_pdf_path) as probe:
        rect = probe[0].search_for("123-45-6789")[0]
    db_session.add(
        Redaction(
            id=uuid.uuid4(),
            document_id=doc1.id,
            page_number=0,
            x=rect.x0 - 1,
            y=rect.y0 - 1,
            width=rect.width + 2,
            height=rect.height + 2,
            created_by_id=user.id,
        )
    )

    job = ExportJob(
        id=uuid.uuid4(),
        case_id=case.id,
        export_type=ExportType.combined_pdf,
        document_ids=[str(doc1.id), str(doc2.id)],
        requested_by_id=user.id,
    )
    db_session.add(job)
    await db_session.commit()

    await run_export(job.id, db_session)

    refreshed = await db_session.get(ExportJob, job.id)
    assert refreshed.status == ExportStatus.completed
    assert refreshed.output_storage_path.endswith("combined.pdf")

    with fitz.open(refreshed.output_storage_path) as merged:
        assert merged.page_count == 2
        assert "123-45-6789" not in merged[0].get_text()
        assert "First doc" in merged[0].get_text()
        assert "Second doc" in merged[1].get_text()

    # the canonical rendered PDF must never be mutated by export
    with fitz.open(doc1.rendered_pdf_path) as original:
        assert "123-45-6789" in original[0].get_text()


async def test_export_production_set_applies_sequential_bates_and_writes_log(db_session, tmp_path):
    user, case, custodian = await _make_case(db_session)

    doc1 = Document(
        id=uuid.uuid4(),
        case_id=case.id,
        custodian_id=custodian.id,
        doc_type=DocType.email,
        subject="A",
        content_hash=str(uuid.uuid4()),
        rendered_pdf_path=_write_pdf(tmp_path, "a.pdf", "Document A"),
        rendered_pdf_page_count=1,
    )
    doc2 = Document(
        id=uuid.uuid4(),
        case_id=case.id,
        custodian_id=custodian.id,
        doc_type=DocType.email,
        subject="B",
        content_hash=str(uuid.uuid4()),
        rendered_pdf_path=_write_pdf(tmp_path, "b.pdf", "Document B"),
        rendered_pdf_page_count=1,
    )
    db_session.add_all([doc1, doc2])
    await db_session.flush()

    job = ExportJob(
        id=uuid.uuid4(),
        case_id=case.id,
        export_type=ExportType.production_set,
        apply_bates=True,
        bates_prefix="ABC",
        bates_start_number=1,
        bates_digit_padding=6,
        document_ids=[str(doc1.id), str(doc2.id)],
        requested_by_id=user.id,
    )
    db_session.add(job)
    await db_session.commit()

    await run_export(job.id, db_session)

    refreshed = await db_session.get(ExportJob, job.id)
    assert refreshed.status == ExportStatus.completed
    assert refreshed.output_storage_path.endswith(".zip")

    with zipfile.ZipFile(refreshed.output_storage_path) as zf:
        names = sorted(zf.namelist())
        assert "ABC000001-ABC000001.pdf" in names
        assert "ABC000002-ABC000002.pdf" in names
        assert "bates_log.csv" in names
        with zf.open("ABC000001-ABC000001.pdf") as f:
            with fitz.open(stream=f.read(), filetype="pdf") as pdf:
                assert "ABC000001" in pdf[0].get_text()
                assert "Document A" in pdf[0].get_text()

    from sqlalchemy import select

    from app.models.export import ExportDocumentBates

    result = await db_session.execute(
        select(ExportDocumentBates).where(ExportDocumentBates.export_job_id == job.id)
    )
    bates_rows = {row.document_id: row for row in result.scalars().all()}
    assert bates_rows[doc1.id].bates_start == "ABC000001"
    assert bates_rows[doc2.id].bates_start == "ABC000002"


async def test_export_production_set_without_bates_uses_document_id_filenames(db_session, tmp_path):
    user, case, custodian = await _make_case(db_session)
    doc = Document(
        id=uuid.uuid4(),
        case_id=case.id,
        custodian_id=custodian.id,
        doc_type=DocType.email,
        subject="A",
        content_hash=str(uuid.uuid4()),
        rendered_pdf_path=_write_pdf(tmp_path, "a.pdf", "Document A"),
        rendered_pdf_page_count=1,
    )
    db_session.add(doc)
    await db_session.flush()

    job = ExportJob(
        id=uuid.uuid4(),
        case_id=case.id,
        export_type=ExportType.production_set,
        apply_bates=False,
        document_ids=[str(doc.id)],
        requested_by_id=user.id,
    )
    db_session.add(job)
    await db_session.commit()

    await run_export(job.id, db_session)

    refreshed = await db_session.get(ExportJob, job.id)
    assert refreshed.status == ExportStatus.completed
    with zipfile.ZipFile(refreshed.output_storage_path) as zf:
        assert zf.namelist() == [f"{doc.id}.pdf"]


async def test_export_marks_job_failed_on_missing_documents_gracefully(db_session):
    user, case, _ = await _make_case(db_session)
    job = ExportJob(
        id=uuid.uuid4(),
        case_id=case.id,
        export_type=ExportType.combined_pdf,
        document_ids=[str(uuid.uuid4())],
        requested_by_id=user.id,
    )
    db_session.add(job)
    await db_session.commit()

    await run_export(job.id, db_session)

    refreshed = await db_session.get(ExportJob, job.id)
    # No resolvable documents (the id doesn't exist) -> PyMuPDF refuses to save a
    # zero-page PDF. The job should fail clearly rather than crash uncaught or
    # silently produce a bogus "success" with no output.
    assert refreshed.status == ExportStatus.failed
    assert refreshed.error_message
