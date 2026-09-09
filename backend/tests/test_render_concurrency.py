import threading
import time
import uuid

import fitz

from app.models.case import Case, Custodian
from app.models.document import DedupStatus, DocType, Document
from app.models.importjob import PSTImportJob
from app.models.user import User
from app.tasks import render_tasks


def _tiny_pdf_bytes() -> bytes:
    doc = fitz.open()
    doc.new_page()
    return doc.tobytes()


async def _make_case_and_job(db_session) -> tuple[Case, PSTImportJob]:
    user = User(id=uuid.uuid4(), email=f"{uuid.uuid4()}@x.com", hashed_password="x", full_name="")
    db_session.add(user)
    await db_session.flush()

    case = Case(id=uuid.uuid4(), name="Render concurrency case", description="", created_by_id=user.id)
    db_session.add(case)
    custodian = Custodian(id=uuid.uuid4(), case_id=case.id, name="Jane", email="")
    db_session.add(custodian)
    await db_session.flush()

    job = PSTImportJob(
        id=uuid.uuid4(),
        case_id=case.id,
        custodian_id=custodian.id,
        uploaded_filename="sample.pst",
        storage_path="/tmp/sample.pst",
        created_by_id=user.id,
    )
    db_session.add(job)
    await db_session.commit()
    return case, job


async def test_render_documents_for_job_renders_concurrently(db_session, monkeypatch):
    monkeypatch.setattr(render_tasks.settings, "render_concurrency", 3)

    case, job = await _make_case_and_job(db_session)
    documents = [
        Document(
            id=uuid.uuid4(),
            case_id=case.id,
            import_job_id=job.id,
            doc_type=DocType.email,
            dedup_status=DedupStatus.primary,
            subject=f"Doc {i}",
            body_text="hello",
            content_hash=str(uuid.uuid4()),
        )
        for i in range(6)
    ]
    db_session.add_all(documents)
    await db_session.commit()

    pdf_bytes = _tiny_pdf_bytes()
    lock = threading.Lock()
    state = {"current": 0, "max": 0}

    def _fake_render_document_bytes(document):
        with lock:
            state["current"] += 1
            state["max"] = max(state["max"], state["current"])
        time.sleep(0.2)
        with lock:
            state["current"] -= 1
        return pdf_bytes

    monkeypatch.setattr(render_tasks, "render_document_bytes", _fake_render_document_bytes)

    await render_tasks.render_documents_for_job(job.id, db_session)

    assert state["max"] >= 2, "documents should render concurrently, not one at a time"
    assert state["max"] <= 3, "concurrency should be bounded by settings.render_concurrency"

    for document in documents:
        await db_session.refresh(document)
        assert document.rendered_pdf_path
        assert document.render_error == ""


async def test_render_documents_for_job_respects_lower_concurrency_setting(db_session, monkeypatch):
    monkeypatch.setattr(render_tasks.settings, "render_concurrency", 1)

    case, job = await _make_case_and_job(db_session)
    documents = [
        Document(
            id=uuid.uuid4(),
            case_id=case.id,
            import_job_id=job.id,
            doc_type=DocType.email,
            dedup_status=DedupStatus.primary,
            subject=f"Doc {i}",
            body_text="hello",
            content_hash=str(uuid.uuid4()),
        )
        for i in range(3)
    ]
    db_session.add_all(documents)
    await db_session.commit()

    pdf_bytes = _tiny_pdf_bytes()
    lock = threading.Lock()
    state = {"current": 0, "max": 0}

    def _fake_render_document_bytes(document):
        with lock:
            state["current"] += 1
            state["max"] = max(state["max"], state["current"])
        time.sleep(0.05)
        with lock:
            state["current"] -= 1
        return pdf_bytes

    monkeypatch.setattr(render_tasks, "render_document_bytes", _fake_render_document_bytes)

    await render_tasks.render_documents_for_job(job.id, db_session)

    assert state["max"] == 1
