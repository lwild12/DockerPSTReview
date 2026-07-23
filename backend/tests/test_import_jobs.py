from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.conftest import register_and_login


async def _setup_case_with_custodian(client: AsyncClient):
    await register_and_login(client, "admin@example.com")
    case_resp = await client.post("/api/cases", json={"name": "Case A"})
    case_id = case_resp.json()["id"]
    custodian_resp = await client.post(
        f"/api/cases/{case_id}/custodians", json={"name": "John Smith"}
    )
    custodian_id = custodian_resp.json()["id"]
    return case_id, custodian_id


async def test_create_import_job_rejects_non_pst_file(client):
    case_id, custodian_id = await _setup_case_with_custodian(client)

    resp = await client.post(
        f"/api/cases/{case_id}/import-jobs",
        data={"custodian_id": custodian_id},
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 400


async def test_create_import_job_enqueues_and_lists(client):
    case_id, custodian_id = await _setup_case_with_custodian(client)

    resp = await client.post(
        f"/api/cases/{case_id}/import-jobs",
        data={"custodian_id": custodian_id},
        files={"file": ("sample.pst", b"fake pst bytes", "application/octet-stream")},
    )
    assert resp.status_code == 201
    job = resp.json()
    assert job["uploaded_filename"] == "sample.pst"
    assert job["case_id"] == case_id

    listed = await client.get(f"/api/cases/{case_id}/import-jobs")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    detail = await client.get(f"/api/cases/{case_id}/import-jobs/{job['id']}")
    assert detail.status_code == 200
    assert detail.json()["id"] == job["id"]


async def test_reviewer_cannot_create_import_job_but_can_view(client):
    case_id, custodian_id = await _setup_case_with_custodian(client)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as reviewer_client:
        reviewer = await register_and_login(reviewer_client, "reviewer@example.com")
        await client.post(
            f"/api/cases/{case_id}/members",
            json={"email": reviewer["email"], "role": "reviewer"},
        )

        forbidden = await reviewer_client.post(
            f"/api/cases/{case_id}/import-jobs",
            data={"custodian_id": custodian_id},
            files={"file": ("sample.pst", b"fake pst bytes", "application/octet-stream")},
        )
        assert forbidden.status_code == 403

        allowed = await reviewer_client.get(f"/api/cases/{case_id}/import-jobs")
        assert allowed.status_code == 200


async def test_import_job_reports_rendering_progress(client, db_session):
    import uuid

    from app.models.document import DedupStatus, DocType, Document

    case_id, custodian_id = await _setup_case_with_custodian(client)

    create_resp = await client.post(
        f"/api/cases/{case_id}/import-jobs",
        data={"custodian_id": custodian_id},
        files={"file": ("sample.pst", b"fake pst bytes", "application/octet-stream")},
    )
    job_id = create_resp.json()["id"]

    def _doc(**overrides):
        defaults = dict(
            id=uuid.uuid4(),
            case_id=uuid.UUID(case_id),
            import_job_id=uuid.UUID(job_id),
            doc_type=DocType.email,
            dedup_status=DedupStatus.primary,
            content_hash=str(uuid.uuid4()),
        )
        defaults.update(overrides)
        return Document(**defaults)

    db_session.add(_doc(rendered_pdf_path="/data/a.pdf", rendered_pdf_page_count=1))
    db_session.add(_doc(render_error="LibreOffice timed out"))
    db_session.add(_doc())  # still pending
    db_session.add(_doc(dedup_status=DedupStatus.duplicate))  # never rendered by design
    await db_session.commit()

    detail = await client.get(f"/api/cases/{case_id}/import-jobs/{job_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["documents_total"] == 3  # duplicate excluded
    assert body["documents_rendered"] == 1
    assert body["documents_render_failed"] == 1

    listed = await client.get(f"/api/cases/{case_id}/import-jobs")
    listed_job = next(j for j in listed.json() if j["id"] == job_id)
    assert listed_job["documents_total"] == 3
    assert listed_job["documents_rendered"] == 1
    assert listed_job["documents_render_failed"] == 1
