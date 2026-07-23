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


async def test_create_review_set_and_add_documents(client, db_session):
    case_id = await _setup_case(client)
    doc1 = await _seed_document(db_session, case_id)
    doc2 = await _seed_document(db_session, case_id)

    create = await client.post(f"/api/cases/{case_id}/review-sets", json={"name": "Hot docs"})
    assert create.status_code == 201
    review_set_id = create.json()["id"]

    add_resp = await client.post(
        f"/api/cases/{case_id}/review-sets/{review_set_id}/documents",
        json={"document_ids": [str(doc1.id), str(doc2.id)]},
    )
    assert add_resp.status_code == 201
    assert len(add_resp.json()) == 2

    # adding the same documents again should not create duplicate rows
    add_again = await client.post(
        f"/api/cases/{case_id}/review-sets/{review_set_id}/documents",
        json={"document_ids": [str(doc1.id)]},
    )
    assert add_again.status_code == 201
    assert add_again.json() == []

    listed = await client.get(f"/api/cases/{case_id}/review-sets/{review_set_id}/documents")
    assert len(listed.json()) == 2
    assert all(d["review_status"] == "unreviewed" for d in listed.json())


async def test_add_documents_from_another_case_is_ignored(client, db_session):
    case_id = await _setup_case(client)
    other_case_resp = await client.post("/api/cases", json={"name": "Other case"})
    other_case_id = other_case_resp.json()["id"]
    foreign_doc = await _seed_document(db_session, other_case_id)

    review_set = await client.post(f"/api/cases/{case_id}/review-sets", json={"name": "RS"})
    review_set_id = review_set.json()["id"]

    add_resp = await client.post(
        f"/api/cases/{case_id}/review-sets/{review_set_id}/documents",
        json={"document_ids": [str(foreign_doc.id)]},
    )
    assert add_resp.status_code == 201
    assert add_resp.json() == []


async def test_update_review_status_sets_reviewer_and_timestamp(client, db_session):
    case_id = await _setup_case(client)
    doc = await _seed_document(db_session, case_id)
    review_set = await client.post(f"/api/cases/{case_id}/review-sets", json={"name": "RS"})
    review_set_id = review_set.json()["id"]
    await client.post(
        f"/api/cases/{case_id}/review-sets/{review_set_id}/documents",
        json={"document_ids": [str(doc.id)]},
    )

    update_resp = await client.patch(
        f"/api/cases/{case_id}/review-sets/{review_set_id}/documents/{doc.id}",
        json={"review_status": "reviewed", "notes": "Looks fine"},
    )
    assert update_resp.status_code == 200
    body = update_resp.json()
    assert body["review_status"] == "reviewed"
    assert body["notes"] == "Looks fine"
    assert body["reviewed_at"] is not None
    assert body["reviewed_by_id"] is not None


async def test_update_document_not_in_review_set_returns_404(client, db_session):
    case_id = await _setup_case(client)
    doc = await _seed_document(db_session, case_id)
    review_set = await client.post(f"/api/cases/{case_id}/review-sets", json={"name": "RS"})
    review_set_id = review_set.json()["id"]

    resp = await client.patch(
        f"/api/cases/{case_id}/review-sets/{review_set_id}/documents/{doc.id}",
        json={"review_status": "reviewed"},
    )
    assert resp.status_code == 404


async def test_reviewer_can_manage_review_sets_but_viewer_cannot(client, db_session):
    case_id = await _setup_case(client)
    doc = await _seed_document(db_session, case_id)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as reviewer_client:
        reviewer = await register_and_login(reviewer_client, "reviewer@example.com")
        await client.post(
            f"/api/cases/{case_id}/members",
            json={"user_id": reviewer["id"], "role": "reviewer"},
        )
        created = await reviewer_client.post(
            f"/api/cases/{case_id}/review-sets", json={"name": "Reviewer set"}
        )
        assert created.status_code == 201
        review_set_id = created.json()["id"]

        added = await reviewer_client.post(
            f"/api/cases/{case_id}/review-sets/{review_set_id}/documents",
            json={"document_ids": [str(doc.id)]},
        )
        assert added.status_code == 201

    async with AsyncClient(transport=transport, base_url="http://test") as viewer_client:
        viewer = await register_and_login(viewer_client, "viewer@example.com")
        await client.post(
            f"/api/cases/{case_id}/members",
            json={"user_id": viewer["id"], "role": "viewer"},
        )
        forbidden = await viewer_client.post(
            f"/api/cases/{case_id}/review-sets", json={"name": "Viewer set"}
        )
        assert forbidden.status_code == 403

        allowed_list = await viewer_client.get(f"/api/cases/{case_id}/review-sets")
        assert allowed_list.status_code == 200
