import uuid

from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.document import DocType, Document
from tests.conftest import register_and_login


async def _setup_case(client):
    await register_and_login(client, "admin@example.com")
    case_resp = await client.post("/api/cases", json={"name": "Case A"})
    return case_resp.json()["id"]


async def _seed_rendered_document(db_session, case_id, tmp_path, name="doc.pdf") -> Document:
    import fitz

    pdf_path = tmp_path / name
    doc = fitz.open()
    doc.new_page(width=612, height=792).insert_text((72, 72), "content")
    doc.save(str(pdf_path))

    document = Document(
        id=uuid.uuid4(),
        case_id=uuid.UUID(case_id),
        doc_type=DocType.email,
        subject="Test",
        content_hash=str(uuid.uuid4()),
        rendered_pdf_path=str(pdf_path),
        rendered_pdf_page_count=1,
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)
    return document


async def test_create_export_job_with_explicit_document_ids(client, db_session, tmp_path):
    case_id = await _setup_case(client)
    doc = await _seed_rendered_document(db_session, case_id, tmp_path)

    resp = await client.post(
        f"/api/cases/{case_id}/export-jobs",
        json={"document_ids": [str(doc.id)], "export_type": "combined_pdf"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["document_ids"] == [str(doc.id)]
    assert body["status"] in ("pending", "running", "completed")

    listed = await client.get(f"/api/cases/{case_id}/export-jobs")
    assert len(listed.json()) == 1


async def test_create_export_job_requires_a_source(client):
    case_id = await _setup_case(client)
    resp = await client.post(
        f"/api/cases/{case_id}/export-jobs", json={"export_type": "combined_pdf"}
    )
    assert resp.status_code == 422


async def test_create_export_job_with_no_resolvable_documents_returns_400(client):
    case_id = await _setup_case(client)
    resp = await client.post(
        f"/api/cases/{case_id}/export-jobs",
        json={"document_ids": [str(uuid.uuid4())], "export_type": "combined_pdf"},
    )
    assert resp.status_code == 400


async def test_download_before_completion_returns_409(client, db_session, tmp_path):
    case_id = await _setup_case(client)
    doc = await _seed_rendered_document(db_session, case_id, tmp_path)

    create = await client.post(
        f"/api/cases/{case_id}/export-jobs",
        json={"document_ids": [str(doc.id)], "export_type": "combined_pdf"},
    )
    job_id = create.json()["id"]

    # the worker isn't running in this test, so the job should still be pending
    resp = await client.get(f"/api/cases/{case_id}/export-jobs/{job_id}/download")
    assert resp.status_code == 409


async def test_reviewer_cannot_create_export_job_but_can_view(client, db_session, tmp_path):
    case_id = await _setup_case(client)
    doc = await _seed_rendered_document(db_session, case_id, tmp_path)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as reviewer_client:
        reviewer = await register_and_login(reviewer_client, "reviewer@example.com")
        await client.post(
            f"/api/cases/{case_id}/members",
            json={"user_id": reviewer["id"], "role": "reviewer"},
        )
        forbidden = await reviewer_client.post(
            f"/api/cases/{case_id}/export-jobs",
            json={"document_ids": [str(doc.id)], "export_type": "combined_pdf"},
        )
        assert forbidden.status_code == 403

        allowed_list = await reviewer_client.get(f"/api/cases/{case_id}/export-jobs")
        assert allowed_list.status_code == 200
