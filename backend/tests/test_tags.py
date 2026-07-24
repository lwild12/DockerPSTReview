import uuid

from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.document import DocType, Document
from tests.conftest import register_and_login


async def _setup_case(client):
    await register_and_login(client, "admin@example.com")
    case_resp = await client.post("/api/cases", json={"name": "Case A"})
    return case_resp.json()["id"]


async def _seed_document(db_session, case_id) -> Document:
    document = Document(
        id=uuid.uuid4(),
        case_id=uuid.UUID(case_id),
        doc_type=DocType.email,
        subject="Test",
        content_hash=str(uuid.uuid4()),
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)
    return document


async def test_create_list_update_delete_tag(client):
    case_id = await _setup_case(client)

    create = await client.post(f"/api/cases/{case_id}/tags", json={"name": "Privileged"})
    assert create.status_code == 201
    tag_id = create.json()["id"]
    assert create.json()["color"] == "#6366f1"

    duplicate = await client.post(f"/api/cases/{case_id}/tags", json={"name": "Privileged"})
    assert duplicate.status_code == 409

    listed = await client.get(f"/api/cases/{case_id}/tags")
    assert len(listed.json()) == 1

    updated = await client.patch(f"/api/cases/{case_id}/tags/{tag_id}", json={"color": "#ff0000"})
    assert updated.status_code == 200
    assert updated.json()["color"] == "#ff0000"
    assert updated.json()["name"] == "Privileged"

    deleted = await client.delete(f"/api/cases/{case_id}/tags/{tag_id}")
    assert deleted.status_code == 204

    listed_after = await client.get(f"/api/cases/{case_id}/tags")
    assert len(listed_after.json()) == 0


async def test_apply_and_remove_tag_on_document(client, db_session):
    case_id = await _setup_case(client)
    document = await _seed_document(db_session, case_id)
    tag_resp = await client.post(f"/api/cases/{case_id}/tags", json={"name": "Hot"})
    tag_id = tag_resp.json()["id"]

    apply_resp = await client.post(f"/api/cases/{case_id}/documents/{document.id}/tags/{tag_id}")
    assert apply_resp.status_code == 201

    detail = await client.get(f"/api/cases/{case_id}/documents/{document.id}")
    assert [t["name"] for t in detail.json()["tags"]] == ["Hot"]

    # applying the same tag twice is idempotent, not an error
    apply_again = await client.post(f"/api/cases/{case_id}/documents/{document.id}/tags/{tag_id}")
    assert apply_again.status_code == 201

    remove_resp = await client.delete(f"/api/cases/{case_id}/documents/{document.id}/tags/{tag_id}")
    assert remove_resp.status_code == 204

    detail_after = await client.get(f"/api/cases/{case_id}/documents/{document.id}")
    assert detail_after.json()["tags"] == []


async def test_reviewer_can_tag_but_only_admin_can_delete_tag_definition(client, db_session):
    case_id = await _setup_case(client)
    document = await _seed_document(db_session, case_id)
    tag_resp = await client.post(f"/api/cases/{case_id}/tags", json={"name": "Confidential"})
    tag_id = tag_resp.json()["id"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as reviewer_client:
        reviewer = await register_and_login(reviewer_client, "reviewer@example.com")
        await client.post(
            f"/api/cases/{case_id}/members",
            json={"email": reviewer["email"], "role": "reviewer"},
        )

        apply_resp = await reviewer_client.post(
            f"/api/cases/{case_id}/documents/{document.id}/tags/{tag_id}"
        )
        assert apply_resp.status_code == 201

        forbidden_delete = await reviewer_client.delete(f"/api/cases/{case_id}/tags/{tag_id}")
        assert forbidden_delete.status_code == 403


async def test_apply_tag_bulk(client, db_session):
    case_id = await _setup_case(client)
    doc1 = await _seed_document(db_session, case_id)
    doc2 = await _seed_document(db_session, case_id)
    other_case_id = (
        (await client.post("/api/cases", json={"name": "Other case"})).json()["id"]
    )
    foreign_doc = await _seed_document(db_session, other_case_id)
    tag_resp = await client.post(f"/api/cases/{case_id}/tags", json={"name": "Bulk"})
    tag_id = tag_resp.json()["id"]

    bulk_resp = await client.post(
        f"/api/cases/{case_id}/tags/{tag_id}/apply-bulk",
        json={"document_ids": [str(doc1.id), str(doc2.id), str(foreign_doc.id)]},
    )
    assert bulk_resp.status_code == 200
    # only the two documents in this case get tagged; the foreign one is silently skipped
    assert bulk_resp.json() == {"tagged_count": 2}

    detail1 = await client.get(f"/api/cases/{case_id}/documents/{doc1.id}")
    assert [t["name"] for t in detail1.json()["tags"]] == ["Bulk"]
    detail2 = await client.get(f"/api/cases/{case_id}/documents/{doc2.id}")
    assert [t["name"] for t in detail2.json()["tags"]] == ["Bulk"]

    # re-applying in bulk to an already-tagged document is idempotent
    again = await client.post(
        f"/api/cases/{case_id}/tags/{tag_id}/apply-bulk",
        json={"document_ids": [str(doc1.id)]},
    )
    assert again.status_code == 200
    assert again.json() == {"tagged_count": 0}


async def test_apply_tag_to_missing_document_or_tag_returns_404(client, db_session):
    case_id = await _setup_case(client)
    document = await _seed_document(db_session, case_id)
    tag_resp = await client.post(f"/api/cases/{case_id}/tags", json={"name": "X"})
    tag_id = tag_resp.json()["id"]

    missing_doc = await client.post(f"/api/cases/{case_id}/documents/{uuid.uuid4()}/tags/{tag_id}")
    assert missing_doc.status_code == 404

    missing_tag = await client.post(
        f"/api/cases/{case_id}/documents/{document.id}/tags/{uuid.uuid4()}"
    )
    assert missing_tag.status_code == 404
