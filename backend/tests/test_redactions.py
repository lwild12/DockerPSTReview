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


async def test_case_redaction_log_lists_across_documents_with_document_info(client, db_session):
    case_id = await _setup_case(client)
    doc1 = await _seed_document(db_session, case_id)
    doc1.subject = "First doc"
    doc1.sender = "alice@example.com"
    doc2 = await _seed_document(db_session, case_id)
    doc2.subject = "Second doc"
    doc2.sender = "bob@example.com"
    await db_session.commit()

    await client.post(
        f"/api/cases/{case_id}/documents/{doc1.id}/redactions",
        json={"page_number": 0, "x": 0, "y": 0, "width": 10, "height": 10, "reason": "PII"},
    )
    await client.post(
        f"/api/cases/{case_id}/documents/{doc2.id}/redactions",
        json={"page_number": 1, "x": 5, "y": 5, "width": 20, "height": 20, "reason": "Privileged"},
    )

    log = await client.get(f"/api/cases/{case_id}/redactions")
    assert log.status_code == 200
    entries = log.json()
    assert len(entries) == 2
    by_subject = {e["document_subject"]: e for e in entries}
    assert by_subject["First doc"]["reason"] == "PII"
    assert by_subject["First doc"]["document_sender"] == "alice@example.com"
    assert by_subject["First doc"]["created_by_email"] == "admin@example.com"
    assert by_subject["Second doc"]["reason"] == "Privileged"


async def test_case_redaction_log_csv_export(client, db_session):
    case_id = await _setup_case(client)
    document = await _seed_document(db_session, case_id)
    document.subject = "Exportable doc"
    await db_session.commit()
    await client.post(
        f"/api/cases/{case_id}/documents/{document.id}/redactions",
        json={"page_number": 0, "x": 0, "y": 0, "width": 10, "height": 10, "reason": "SSN"},
    )

    csv_resp = await client.get(f"/api/cases/{case_id}/redactions/export.csv")
    assert csv_resp.status_code == 200
    assert csv_resp.headers["content-type"].startswith("text/csv")
    body = csv_resp.text
    assert "Exportable doc" in body
    assert "SSN" in body
    assert "admin@example.com" in body


async def test_case_redaction_log_excludes_other_cases(client, db_session):
    case_id = await _setup_case(client)
    other_case_resp = await client.post("/api/cases", json={"name": "Other case"})
    other_case_id = other_case_resp.json()["id"]
    other_doc = await _seed_document(db_session, other_case_id)
    await client.post(
        f"/api/cases/{other_case_id}/documents/{other_doc.id}/redactions",
        json={"page_number": 0, "x": 0, "y": 0, "width": 10, "height": 10},
    )

    log = await client.get(f"/api/cases/{case_id}/redactions")
    assert log.status_code == 200
    assert log.json() == []
