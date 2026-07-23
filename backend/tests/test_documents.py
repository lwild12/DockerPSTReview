import uuid

from app.models.document import DedupStatus, DocType, Document, Thread
from tests.conftest import register_and_login


async def _setup_case(client):
    admin = await register_and_login(client, "admin@example.com")
    case_resp = await client.post("/api/cases", json={"name": "Case A"})
    case_id = case_resp.json()["id"]
    return admin, case_id


async def _seed_document(db_session, case_id, **overrides) -> Document:
    defaults = dict(
        id=uuid.uuid4(),
        case_id=uuid.UUID(case_id),
        doc_type=DocType.email,
        subject="Test subject",
        sender="a@x.com",
        recipients_to=["b@x.com"],
        body_text="hello",
        content_hash=str(uuid.uuid4()),
    )
    defaults.update(overrides)
    document = Document(**defaults)
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)
    return document


async def test_list_documents_filters_by_doc_type_and_search(client, db_session):
    _, case_id = await _setup_case(client)
    await _seed_document(db_session, case_id, subject="Budget report", doc_type=DocType.email)
    await _seed_document(
        db_session, case_id, subject="photo.jpg", doc_type=DocType.attachment, sender=""
    )

    all_docs = await client.get(f"/api/cases/{case_id}/documents")
    assert all_docs.status_code == 200
    assert len(all_docs.json()) == 2

    only_attachments = await client.get(
        f"/api/cases/{case_id}/documents", params={"doc_type": "attachment"}
    )
    assert len(only_attachments.json()) == 1
    assert only_attachments.json()[0]["subject"] == "photo.jpg"

    search = await client.get(f"/api/cases/{case_id}/documents", params={"q": "Budget"})
    assert len(search.json()) == 1
    assert search.json()[0]["subject"] == "Budget report"


async def test_get_document_detail_and_pdf_missing(client, db_session):
    _, case_id = await _setup_case(client)
    document = await _seed_document(db_session, case_id)

    detail = await client.get(f"/api/cases/{case_id}/documents/{document.id}")
    assert detail.status_code == 200
    assert detail.json()["subject"] == "Test subject"

    pdf_resp = await client.get(f"/api/cases/{case_id}/documents/{document.id}/pdf")
    assert pdf_resp.status_code == 404


async def test_document_not_found_returns_404(client, db_session):
    _, case_id = await _setup_case(client)
    missing_id = uuid.uuid4()
    resp = await client.get(f"/api/cases/{case_id}/documents/{missing_id}")
    assert resp.status_code == 404


async def test_thread_documents_endpoint(client, db_session):
    _, case_id = await _setup_case(client)
    thread = Thread(id=uuid.uuid4(), case_id=uuid.UUID(case_id))
    db_session.add(thread)
    await db_session.commit()

    doc1 = await _seed_document(db_session, case_id, subject="root", thread_id=thread.id)
    doc2 = await _seed_document(db_session, case_id, subject="reply", thread_id=thread.id)
    await _seed_document(db_session, case_id, subject="unrelated")

    resp = await client.get(f"/api/cases/{case_id}/threads/{thread.id}/documents")
    assert resp.status_code == 200
    subjects = {d["subject"] for d in resp.json()}
    assert subjects == {"root", "reply"}
    assert {doc1.id, doc2.id} == {uuid.UUID(d["id"]) for d in resp.json()}


async def test_reviewer_can_list_but_admin_only_endpoints_are_gated(client, db_session):
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    _, case_id = await _setup_case(client)
    await _seed_document(db_session, case_id)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as reviewer_client:
        reviewer = await register_and_login(reviewer_client, "reviewer@example.com")
        await client.post(
            f"/api/cases/{case_id}/members",
            json={"user_id": reviewer["id"], "role": "reviewer"},
        )
        resp = await reviewer_client.get(f"/api/cases/{case_id}/documents")
        assert resp.status_code == 200


async def test_non_member_cannot_list_documents(client, db_session):
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    _, case_id = await _setup_case(client)
    await _seed_document(db_session, case_id)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as outsider_client:
        await register_and_login(outsider_client, "outsider@example.com")
        resp = await outsider_client.get(f"/api/cases/{case_id}/documents")
        assert resp.status_code == 403


async def test_dedup_status_filter(client, db_session):
    _, case_id = await _setup_case(client)
    primary = await _seed_document(db_session, case_id, dedup_status=DedupStatus.primary)
    await _seed_document(
        db_session, case_id, dedup_status=DedupStatus.duplicate, duplicate_of_id=primary.id
    )

    resp = await client.get(f"/api/cases/{case_id}/documents", params={"dedup_status": "duplicate"})
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["dedup_status"] == "duplicate"
