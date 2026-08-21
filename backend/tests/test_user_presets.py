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


async def test_creating_a_tag_saves_it_as_a_personal_preset(client, db_session):
    case_id = await _setup_case(client)

    create = await client.post(
        f"/api/cases/{case_id}/tags", json={"name": "PII", "color": "#ff0000"}
    )
    assert create.status_code == 201

    presets = await client.get("/api/me/tag-presets")
    assert presets.status_code == 200
    assert [p["name"] for p in presets.json()] == ["PII"]
    assert presets.json()[0]["color"] == "#ff0000"


async def test_tag_preset_from_one_case_is_suggested_in_another_case_for_same_user(
    client, db_session
):
    case_id = await _setup_case(client)
    await client.post(f"/api/cases/{case_id}/tags", json={"name": "Privileged"})

    other_case = await client.post("/api/cases", json={"name": "Case B"})
    other_case_id = other_case.json()["id"]

    # Not materialized into the second case automatically -- only suggested.
    other_case_tags = await client.get(f"/api/cases/{other_case_id}/tags")
    assert other_case_tags.json() == []

    presets = await client.get("/api/me/tag-presets")
    assert [p["name"] for p in presets.json()] == ["Privileged"]

    # The frontend materializes it on first use by calling the normal create-tag
    # endpoint in the new case; the preset itself is unaffected (idempotent upsert).
    materialize = await client.post(
        f"/api/cases/{other_case_id}/tags", json={"name": "Privileged", "color": "#6366f1"}
    )
    assert materialize.status_code == 201
    presets_after = await client.get("/api/me/tag-presets")
    assert len(presets_after.json()) == 1


async def test_tag_presets_are_private_to_the_creating_user(client, db_session):
    case_id = await _setup_case(client)
    await client.post(f"/api/cases/{case_id}/tags", json={"name": "Confidential"})

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as other_client:
        await register_and_login(other_client, "someoneelse@example.com")
        other_presets = await other_client.get("/api/me/tag-presets")
        assert other_presets.json() == []


async def test_delete_tag_preset(client, db_session):
    case_id = await _setup_case(client)
    await client.post(f"/api/cases/{case_id}/tags", json={"name": "Temp"})
    preset_id = (await client.get("/api/me/tag-presets")).json()[0]["id"]

    deleted = await client.delete(f"/api/me/tag-presets/{preset_id}")
    assert deleted.status_code == 204

    presets_after = await client.get("/api/me/tag-presets")
    assert presets_after.json() == []

    missing = await client.delete(f"/api/me/tag-presets/{preset_id}")
    assert missing.status_code == 404


async def test_setting_a_redaction_reason_saves_it_as_a_personal_preset(client, db_session):
    case_id = await _setup_case(client)
    document = await _seed_document(db_session, case_id)

    create = await client.post(
        f"/api/cases/{case_id}/documents/{document.id}/redactions",
        json={"page_number": 0, "x": 0, "y": 0, "width": 10, "height": 10, "reason": "SSN - PII"},
    )
    assert create.status_code == 201

    presets = await client.get("/api/me/redaction-reason-presets")
    assert [p["reason"] for p in presets.json()] == ["SSN - PII"]


async def test_editing_a_redaction_reason_via_patch_also_saves_a_preset(client, db_session):
    case_id = await _setup_case(client)
    document = await _seed_document(db_session, case_id)
    redaction = (
        await client.post(
            f"/api/cases/{case_id}/documents/{document.id}/redactions",
            json={"page_number": 0, "x": 0, "y": 0, "width": 10, "height": 10},
        )
    ).json()

    await client.patch(
        f"/api/cases/{case_id}/documents/{document.id}/redactions/{redaction['id']}",
        json={"reason": "Attorney-client privilege"},
    )

    presets = await client.get("/api/me/redaction-reason-presets")
    assert [p["reason"] for p in presets.json()] == ["Attorney-client privilege"]


async def test_blank_reason_does_not_create_an_empty_preset(client, db_session):
    case_id = await _setup_case(client)
    document = await _seed_document(db_session, case_id)

    await client.post(
        f"/api/cases/{case_id}/documents/{document.id}/redactions",
        json={"page_number": 0, "x": 0, "y": 0, "width": 10, "height": 10},
    )

    presets = await client.get("/api/me/redaction-reason-presets")
    assert presets.json() == []


async def test_delete_redaction_reason_preset(client, db_session):
    case_id = await _setup_case(client)
    document = await _seed_document(db_session, case_id)
    await client.post(
        f"/api/cases/{case_id}/documents/{document.id}/redactions",
        json={"page_number": 0, "x": 0, "y": 0, "width": 10, "height": 10, "reason": "Typo reason"},
    )
    preset_id = (await client.get("/api/me/redaction-reason-presets")).json()[0]["id"]

    deleted = await client.delete(f"/api/me/redaction-reason-presets/{preset_id}")
    assert deleted.status_code == 204

    presets_after = await client.get("/api/me/redaction-reason-presets")
    assert presets_after.json() == []


async def test_unauthenticated_cannot_access_presets(client, db_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as anon_client:
        resp = await anon_client.get("/api/me/tag-presets")
        assert resp.status_code == 401
