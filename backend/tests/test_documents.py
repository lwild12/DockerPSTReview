import uuid

from app.models.ai_review import AiRelevanceStatus, DocumentAiRelevance
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
            json={"email": reviewer["email"], "role": "reviewer"},
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


async def test_content_changed_filter(client, db_session):
    from datetime import UTC, datetime

    _, case_id = await _setup_case(client)
    flagged = await _seed_document(
        db_session, case_id, content_changed_at=datetime.now(UTC), subject="Reprocessed"
    )
    await _seed_document(db_session, case_id, subject="Untouched")

    resp = await client.get(f"/api/cases/{case_id}/documents", params={"content_changed": "true"})
    assert resp.status_code == 200
    assert [d["id"] for d in resp.json()] == [str(flagged.id)]

    resp_false = await client.get(
        f"/api/cases/{case_id}/documents", params={"content_changed": "false"}
    )
    assert resp_false.status_code == 200
    assert [d["subject"] for d in resp_false.json()] == ["Untouched"]


async def test_list_document_attachments(client, db_session):
    _, case_id = await _setup_case(client)
    email = await _seed_document(db_session, case_id, subject="Cover email")
    attachment1 = await _seed_document(
        db_session,
        case_id,
        doc_type=DocType.attachment,
        parent_document_id=email.id,
        subject="report.pdf",
        mime_type="application/pdf",
        file_size=1234,
    )
    await _seed_document(
        db_session,
        case_id,
        doc_type=DocType.attachment,
        parent_document_id=email.id,
        subject="budget.xlsx",
        mime_type="application/vnd.ms-excel",
        file_size=5678,
    )
    await _seed_document(db_session, case_id, subject="unrelated email")

    resp = await client.get(f"/api/cases/{case_id}/documents/{email.id}/attachments")
    assert resp.status_code == 200
    subjects = [a["subject"] for a in resp.json()]
    assert subjects == ["budget.xlsx", "report.pdf"]
    assert all(a["has_native_file"] is False for a in resp.json())

    email_detail = await client.get(f"/api/cases/{case_id}/documents/{email.id}")
    assert email_detail.json()["attachment_count"] == 2
    attachment_detail = await client.get(f"/api/cases/{case_id}/documents/{attachment1.id}")
    assert attachment_detail.json()["attachment_count"] == 0

    empty_resp = await client.get(f"/api/cases/{case_id}/documents/{attachment1.id}/attachments")
    assert empty_resp.status_code == 200
    assert empty_resp.json() == []


async def test_document_attachments_missing_parent_returns_404(client, db_session):
    _, case_id = await _setup_case(client)
    resp = await client.get(f"/api/cases/{case_id}/documents/{uuid.uuid4()}/attachments")
    assert resp.status_code == 404


async def test_get_document_native_file(client, db_session, tmp_path):
    _, case_id = await _setup_case(client)
    native_path = tmp_path / "report.pdf"
    native_path.write_bytes(b"%PDF-1.4 fake native file content")
    attachment = await _seed_document(
        db_session,
        case_id,
        doc_type=DocType.attachment,
        subject="report.pdf",
        mime_type="application/pdf",
        native_file_path=str(native_path),
    )

    detail = await client.get(f"/api/cases/{case_id}/documents/{attachment.id}")
    assert detail.json()["has_native_file"] is True

    resp = await client.get(f"/api/cases/{case_id}/documents/{attachment.id}/native")
    assert resp.status_code == 200
    assert resp.content == b"%PDF-1.4 fake native file content"
    assert resp.headers["content-type"] == "application/pdf"
    assert "report.pdf" in resp.headers["content-disposition"]


async def test_get_document_native_file_missing_returns_404(client, db_session):
    _, case_id = await _setup_case(client)
    document = await _seed_document(db_session, case_id)
    resp = await client.get(f"/api/cases/{case_id}/documents/{document.id}/native")
    assert resp.status_code == 404


async def test_list_documents_pagination_covers_every_row_when_sort_keys_tie(client, db_session):
    # Documents from one PST import batch share the same created_at
    # (Postgres' now() is transaction-scoped) and non-email docs have no
    # sent_at, so without a unique tiebreaker in the ORDER BY, paging
    # through with OFFSET/LIMIT across separate queries isn't guaranteed to
    # visit every row exactly once -- this is exactly what the frontend's
    # "add all documents to a review set" flow relies on.
    _, case_id = await _setup_case(client)
    seeded_ids = set()
    for i in range(7):
        doc = await _seed_document(
            db_session,
            case_id,
            doc_type=DocType.attachment,
            subject=f"attachment {i}",
            sender="",
        )
        seeded_ids.add(doc.id)

    seen_ids: list[uuid.UUID] = []
    page = 1
    page_size = 2
    while True:
        resp = await client.get(
            f"/api/cases/{case_id}/documents",
            params={"page": page, "page_size": page_size},
        )
        assert resp.status_code == 200
        batch = resp.json()
        seen_ids.extend(uuid.UUID(d["id"]) for d in batch)
        if len(batch) < page_size:
            break
        page += 1

    assert set(seen_ids) == seeded_ids
    assert len(seen_ids) == len(seeded_ids), "a document was returned more than once across pages"


async def test_list_and_detail_embed_ai_relevance(client, db_session):
    _, case_id = await _setup_case(client)
    scored = await _seed_document(db_session, case_id, subject="Scored doc")
    unscored = await _seed_document(db_session, case_id, subject="Unscored doc")
    db_session.add(
        DocumentAiRelevance(
            document_id=scored.id,
            status=AiRelevanceStatus.completed,
            score=85,
            rationale="Directly on point.",
            criteria_snapshot="Q3 budget",
        )
    )
    await db_session.commit()

    listed = await client.get(f"/api/cases/{case_id}/documents")
    by_id = {d["id"]: d for d in listed.json()}
    assert by_id[str(scored.id)]["ai_relevance"]["score"] == 85
    assert by_id[str(scored.id)]["ai_relevance"]["status"] == "completed"
    assert by_id[str(unscored.id)]["ai_relevance"] is None

    detail = await client.get(f"/api/cases/{case_id}/documents/{scored.id}")
    assert detail.json()["ai_relevance"]["rationale"] == "Directly on point."


async def test_list_documents_filters_by_ai_relevance(client, db_session):
    _, case_id = await _setup_case(client)
    high = await _seed_document(db_session, case_id, subject="High relevance")
    low = await _seed_document(db_session, case_id, subject="Low relevance")
    await _seed_document(db_session, case_id, subject="Unscored")

    db_session.add_all(
        [
            DocumentAiRelevance(document_id=high.id, status=AiRelevanceStatus.completed, score=90),
            DocumentAiRelevance(document_id=low.id, status=AiRelevanceStatus.completed, score=5),
        ]
    )
    await db_session.commit()

    by_status = await client.get(
        f"/api/cases/{case_id}/documents", params={"ai_relevance_status": "completed"}
    )
    assert {d["id"] for d in by_status.json()} == {str(high.id), str(low.id)}

    by_min_score = await client.get(
        f"/api/cases/{case_id}/documents", params={"ai_relevance_min_score": 50}
    )
    assert {d["id"] for d in by_min_score.json()} == {str(high.id)}
