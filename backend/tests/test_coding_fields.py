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


async def test_create_list_update_delete_coding_field(client):
    case_id = await _setup_case(client)

    create = await client.post(
        f"/api/cases/{case_id}/coding-fields",
        json={
            "name": "Responsiveness",
            "field_type": "single_select",
            "options": ["Responsive", "Not responsive"],
        },
    )
    assert create.status_code == 201
    field_id = create.json()["id"]
    assert create.json()["field_type"] == "single_select"

    no_options = await client.post(
        f"/api/cases/{case_id}/coding-fields",
        json={"name": "Empty", "field_type": "multi_select", "options": []},
    )
    assert no_options.status_code == 422

    duplicate = await client.post(
        f"/api/cases/{case_id}/coding-fields",
        json={"name": "Responsiveness", "field_type": "single_select", "options": ["A"]},
    )
    assert duplicate.status_code == 409

    listed = await client.get(f"/api/cases/{case_id}/coding-fields")
    assert len(listed.json()) == 1

    updated = await client.patch(
        f"/api/cases/{case_id}/coding-fields/{field_id}",
        json={"options": ["Responsive", "Not responsive", "Partially responsive"]},
    )
    assert updated.status_code == 200
    assert len(updated.json()["options"]) == 3

    deleted = await client.delete(f"/api/cases/{case_id}/coding-fields/{field_id}")
    assert deleted.status_code == 204

    listed_after = await client.get(f"/api/cases/{case_id}/coding-fields")
    assert len(listed_after.json()) == 0


async def test_set_single_select_coding_value_replaces_previous(client, db_session):
    case_id = await _setup_case(client)
    document = await _seed_document(db_session, case_id)
    field_resp = await client.post(
        f"/api/cases/{case_id}/coding-fields",
        json={
            "name": "Confidentiality",
            "field_type": "single_select",
            "options": ["Public", "Confidential"],
        },
    )
    field_id = field_resp.json()["id"]

    first = await client.put(
        f"/api/cases/{case_id}/documents/{document.id}/coding-values/{field_id}",
        json={"values": ["Public"]},
    )
    assert first.status_code == 200
    assert [v["value"] for v in first.json()] == ["Public"]

    too_many = await client.put(
        f"/api/cases/{case_id}/documents/{document.id}/coding-values/{field_id}",
        json={"values": ["Public", "Confidential"]},
    )
    assert too_many.status_code == 422

    second = await client.put(
        f"/api/cases/{case_id}/documents/{document.id}/coding-values/{field_id}",
        json={"values": ["Confidential"]},
    )
    assert second.status_code == 200
    assert [v["value"] for v in second.json()] == ["Confidential"]

    listed = await client.get(f"/api/cases/{case_id}/documents/{document.id}/coding-values")
    assert [v["value"] for v in listed.json()] == ["Confidential"]


async def test_set_multi_select_coding_value_allows_multiple(client, db_session):
    case_id = await _setup_case(client)
    document = await _seed_document(db_session, case_id)
    field_resp = await client.post(
        f"/api/cases/{case_id}/coding-fields",
        json={
            "name": "Issues",
            "field_type": "multi_select",
            "options": ["Contract", "IP", "Employment"],
        },
    )
    field_id = field_resp.json()["id"]

    set_resp = await client.put(
        f"/api/cases/{case_id}/documents/{document.id}/coding-values/{field_id}",
        json={"values": ["Contract", "IP"]},
    )
    assert set_resp.status_code == 200
    assert {v["value"] for v in set_resp.json()} == {"Contract", "IP"}

    invalid_option = await client.put(
        f"/api/cases/{case_id}/documents/{document.id}/coding-values/{field_id}",
        json={"values": ["Not-a-real-option"]},
    )
    assert invalid_option.status_code == 422


async def test_reviewer_can_set_values_but_only_admin_manages_field_definitions(client, db_session):
    case_id = await _setup_case(client)
    document = await _seed_document(db_session, case_id)
    field_resp = await client.post(
        f"/api/cases/{case_id}/coding-fields",
        json={
            "name": "Privilege",
            "field_type": "single_select",
            "options": ["Privileged", "Not privileged"],
        },
    )
    field_id = field_resp.json()["id"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as reviewer_client:
        reviewer = await register_and_login(reviewer_client, "reviewer@example.com")
        await client.post(
            f"/api/cases/{case_id}/members",
            json={"email": reviewer["email"], "role": "reviewer"},
        )

        set_resp = await reviewer_client.put(
            f"/api/cases/{case_id}/documents/{document.id}/coding-values/{field_id}",
            json={"values": ["Privileged"]},
        )
        assert set_resp.status_code == 200

        forbidden_create = await reviewer_client.post(
            f"/api/cases/{case_id}/coding-fields",
            json={"name": "New field", "field_type": "single_select", "options": ["A"]},
        )
        assert forbidden_create.status_code == 403

        forbidden_delete = await reviewer_client.delete(
            f"/api/cases/{case_id}/coding-fields/{field_id}"
        )
        assert forbidden_delete.status_code == 403


async def test_set_coding_value_for_missing_document_or_field_returns_404(client, db_session):
    case_id = await _setup_case(client)
    document = await _seed_document(db_session, case_id)
    field_resp = await client.post(
        f"/api/cases/{case_id}/coding-fields",
        json={"name": "X", "field_type": "single_select", "options": ["A"]},
    )
    field_id = field_resp.json()["id"]

    missing_doc = await client.put(
        f"/api/cases/{case_id}/documents/{uuid.uuid4()}/coding-values/{field_id}",
        json={"values": ["A"]},
    )
    assert missing_doc.status_code == 404

    missing_field = await client.put(
        f"/api/cases/{case_id}/documents/{document.id}/coding-values/{uuid.uuid4()}",
        json={"values": ["A"]},
    )
    assert missing_field.status_code == 404
