import uuid

from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.document import DocType, Document
from tests.conftest import register_and_login


async def _setup_case(client):
    await register_and_login(client, "admin@example.com")
    case_resp = await client.post("/api/cases", json={"name": "Case A"})
    return case_resp.json()["id"]


async def _seed_document(db_session, case_id, page_count: int = 3) -> Document:
    document = Document(
        id=uuid.uuid4(),
        case_id=uuid.UUID(case_id),
        doc_type=DocType.email,
        subject="Test",
        content_hash=str(uuid.uuid4()),
        rendered_pdf_page_count=page_count,
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)
    return document


async def test_create_list_update_delete_redaction(client, db_session):
    case_id = await _setup_case(client)
    document = await _seed_document(db_session, case_id)

    create = await client.post(
        f"/api/cases/{case_id}/documents/{document.id}/redactions",
        json={"page_number": 0, "x": 10.0, "y": 20.0, "width": 100.0, "height": 30.0},
    )
    assert create.status_code == 201
    redaction_id = create.json()["id"]
    assert create.json()["color"] == "#000000"

    listed = await client.get(f"/api/cases/{case_id}/documents/{document.id}/redactions")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    updated = await client.patch(
        f"/api/cases/{case_id}/documents/{document.id}/redactions/{redaction_id}",
        json={"width": 150.0, "reason": "PII"},
    )
    assert updated.status_code == 200
    assert updated.json()["width"] == 150.0
    assert updated.json()["reason"] == "PII"
    assert updated.json()["x"] == 10.0  # untouched fields survive a partial update

    deleted = await client.delete(
        f"/api/cases/{case_id}/documents/{document.id}/redactions/{redaction_id}"
    )
    assert deleted.status_code == 204

    listed_after = await client.get(f"/api/cases/{case_id}/documents/{document.id}/redactions")
    assert len(listed_after.json()) == 0


async def test_create_redaction_rejects_out_of_range_page(client, db_session):
    case_id = await _setup_case(client)
    document = await _seed_document(db_session, case_id, page_count=2)

    resp = await client.post(
        f"/api/cases/{case_id}/documents/{document.id}/redactions",
        json={"page_number": 5, "x": 0, "y": 0, "width": 10, "height": 10},
    )
    assert resp.status_code == 400


async def test_redaction_on_missing_document_returns_404(client):
    case_id = await _setup_case(client)
    resp = await client.post(
        f"/api/cases/{case_id}/documents/{uuid.uuid4()}/redactions",
        json={"page_number": 0, "x": 0, "y": 0, "width": 10, "height": 10},
    )
    assert resp.status_code == 404


async def test_reviewer_can_redact_but_viewer_cannot(client, db_session):
    case_id = await _setup_case(client)
    document = await _seed_document(db_session, case_id)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as reviewer_client:
        reviewer = await register_and_login(reviewer_client, "reviewer@example.com")
        await client.post(
            f"/api/cases/{case_id}/members",
            json={"email": reviewer["email"], "role": "reviewer"},
        )
        created = await reviewer_client.post(
            f"/api/cases/{case_id}/documents/{document.id}/redactions",
            json={"page_number": 0, "x": 0, "y": 0, "width": 10, "height": 10},
        )
        assert created.status_code == 201

    async with AsyncClient(transport=transport, base_url="http://test") as viewer_client:
        viewer = await register_and_login(viewer_client, "viewer@example.com")
        await client.post(
            f"/api/cases/{case_id}/members",
            json={"email": viewer["email"], "role": "viewer"},
        )
        forbidden = await viewer_client.post(
            f"/api/cases/{case_id}/documents/{document.id}/redactions",
            json={"page_number": 0, "x": 0, "y": 0, "width": 10, "height": 10},
        )
        assert forbidden.status_code == 403

        allowed_list = await viewer_client.get(
            f"/api/cases/{case_id}/documents/{document.id}/redactions"
        )
        assert allowed_list.status_code == 200


async def test_redaction_spanning_multiple_pages_creates_multiple_rows(client, db_session):
    case_id = await _setup_case(client)
    document = await _seed_document(db_session, case_id, page_count=3)

    for page in range(2):
        resp = await client.post(
            f"/api/cases/{case_id}/documents/{document.id}/redactions",
            json={"page_number": page, "x": 0, "y": 0, "width": 50, "height": 20},
        )
        assert resp.status_code == 201

    listed = await client.get(f"/api/cases/{case_id}/documents/{document.id}/redactions")
    assert len(listed.json()) == 2
    assert {r["page_number"] for r in listed.json()} == {0, 1}
