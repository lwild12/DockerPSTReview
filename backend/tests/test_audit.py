from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.conftest import register_and_login


async def test_case_and_custodian_creation_are_audited(client):
    await register_and_login(client, "admin@example.com")
    resp = await client.post("/api/cases", json={"name": "Case A"})
    case_id = resp.json()["id"]

    await client.post(
        f"/api/cases/{case_id}/custodians", json={"name": "John Smith", "email": "js@example.com"}
    )

    logs = await client.get(f"/api/cases/{case_id}/audit-logs")
    assert logs.status_code == 200
    actions = [entry["action"] for entry in logs.json()]
    assert "case.created" in actions
    assert "custodian.created" in actions
    # newest first
    assert logs.json()[0]["action"] == "custodian.created"


async def test_tag_apply_and_remove_are_audited(client, db_session):
    import uuid

    from app.models.document import DocType, Document

    await register_and_login(client, "admin2@example.com")
    case_resp = await client.post("/api/cases", json={"name": "Case B"})
    case_id = case_resp.json()["id"]

    document = Document(
        id=uuid.uuid4(),
        case_id=uuid.UUID(case_id),
        doc_type=DocType.email,
        subject="Test",
        content_hash=str(uuid.uuid4()),
    )
    db_session.add(document)
    await db_session.commit()

    tag_resp = await client.post(f"/api/cases/{case_id}/tags", json={"name": "hot"})
    tag_id = tag_resp.json()["id"]

    await client.post(f"/api/cases/{case_id}/documents/{document.id}/tags/{tag_id}")
    await client.delete(f"/api/cases/{case_id}/documents/{document.id}/tags/{tag_id}")

    logs = await client.get(f"/api/cases/{case_id}/audit-logs")
    actions = [entry["action"] for entry in logs.json()]
    assert "tag.created" in actions
    assert "tag.applied" in actions
    assert "tag.removed" in actions


async def test_member_add_and_remove_are_audited(client):
    await register_and_login(client, "admin3@example.com")
    case_resp = await client.post("/api/cases", json={"name": "Case C"})
    case_id = case_resp.json()["id"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as other_client:
        reviewer = await register_and_login(other_client, "reviewer4@example.com")

    add_resp = await client.post(
        f"/api/cases/{case_id}/members",
        json={"user_id": reviewer["id"], "role": "reviewer"},
    )
    membership_id = add_resp.json()["id"]

    await client.delete(f"/api/cases/{case_id}/members/{membership_id}")

    logs = await client.get(f"/api/cases/{case_id}/audit-logs")
    actions = [entry["action"] for entry in logs.json()]
    assert "member.added" in actions
    assert "member.removed" in actions


async def test_audit_log_endpoint_requires_admin(client):
    await register_and_login(client, "admin5@example.com")
    case_resp = await client.post("/api/cases", json={"name": "Case D"})
    case_id = case_resp.json()["id"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as reviewer_client:
        reviewer = await register_and_login(reviewer_client, "reviewer5@example.com")

    await client.post(
        f"/api/cases/{case_id}/members",
        json={"user_id": reviewer["id"], "role": "reviewer"},
    )

    async with AsyncClient(transport=transport, base_url="http://test") as reviewer_client:
        await register_and_login(reviewer_client, "reviewer5@example.com")
        denied = await reviewer_client.get(f"/api/cases/{case_id}/audit-logs")
        assert denied.status_code == 403
