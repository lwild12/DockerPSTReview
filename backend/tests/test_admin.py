import uuid

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.main import app
from app.models.user import User
from tests.conftest import register_and_login


async def _make_superuser(client, db_session, email: str) -> dict:
    me = await register_and_login(client, email)
    result = await db_session.execute(select(User).where(User.id == uuid.UUID(me["id"])))
    user = result.scalar_one()
    user.is_superuser = True
    await db_session.commit()
    return me


async def test_non_superuser_cannot_access_admin_endpoints(client, db_session):
    # the first registered user always becomes a superuser, so use a second
    # account (via a separate session) to get a genuinely non-superuser one
    await register_and_login(client, "first@example.com")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as regular_client:
        await register_and_login(regular_client, "regular@example.com")

        forbidden_users = await regular_client.get("/api/admin/users")
        assert forbidden_users.status_code == 403

        forbidden_settings = await regular_client.get("/api/admin/settings")
        assert forbidden_settings.status_code == 403


async def test_superuser_can_list_and_promote_users(client, db_session):
    await _make_superuser(client, db_session, "admin@example.com")
    other = await register_and_login(
        client,  # reuse the same client is fine; register doesn't require logout first
        "other@example.com",
    )
    # registering a second account with the same client logs back in as "other" --
    # log back in as the admin to exercise the admin endpoints
    login_resp = await client.post(
        "/api/auth/login",
        data={"username": "admin@example.com", "password": "SuperSecret123!"},
    )
    assert login_resp.status_code == 204

    listed = await client.get("/api/admin/users")
    assert listed.status_code == 200
    emails = {u["email"] for u in listed.json()}
    assert {"admin@example.com", "other@example.com"} <= emails

    promoted = await client.patch(f"/api/admin/users/{other['id']}", json={"is_superuser": True})
    assert promoted.status_code == 200
    assert promoted.json()["is_superuser"] is True

    deactivated = await client.patch(f"/api/admin/users/{other['id']}", json={"is_active": False})
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False


async def test_superuser_cannot_deactivate_or_demote_self(client, db_session):
    admin = await _make_superuser(client, db_session, "admin2@example.com")

    demote_self = await client.patch(
        f"/api/admin/users/{admin['id']}", json={"is_superuser": False}
    )
    assert demote_self.status_code == 400

    deactivate_self = await client.patch(
        f"/api/admin/users/{admin['id']}", json={"is_active": False}
    )
    assert deactivate_self.status_code == 400


async def test_update_missing_user_returns_404(client, db_session):
    await _make_superuser(client, db_session, "admin3@example.com")
    resp = await client.patch(f"/api/admin/users/{uuid.uuid4()}", json={"is_active": False})
    assert resp.status_code == 404


async def test_get_and_update_system_settings(client, db_session):
    await _make_superuser(client, db_session, "admin4@example.com")

    initial = await client.get("/api/admin/settings")
    assert initial.status_code == 200
    body = initial.json()
    assert "enable_api_docs" in body
    assert "cookie_secure" in body

    updated = await client.patch("/api/admin/settings", json={"enable_api_docs": True})
    assert updated.status_code == 200
    assert updated.json()["enable_api_docs"] is True
    assert updated.json()["updated_by_id"] is not None

    # the setting persists across requests, not just echoed back once
    refetched = await client.get("/api/admin/settings")
    assert refetched.json()["enable_api_docs"] is True


async def test_get_and_update_ollama_settings(client, db_session, monkeypatch):
    from cryptography.fernet import Fernet

    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "secret_encryption_key", Fernet.generate_key().decode())

    await _make_superuser(client, db_session, "admin5@example.com")

    initial = await client.get("/api/admin/settings")
    body = initial.json()
    assert body["ollama_base_url"] == ""
    assert body["ollama_api_key_set"] is False
    assert body["ai_review_concurrency"] == 1
    # Document content is potentially privileged/sensitive -- request/response
    # logging must default off, not on.
    assert body["ollama_log_requests"] is False

    updated = await client.patch(
        "/api/admin/settings",
        json={
            "ollama_base_url": "http://ollama.local:11434",
            "ollama_model": "llama3.1",
            "ollama_api_key": "secret-token",
            "ai_review_concurrency": 3,
            "ollama_log_requests": True,
        },
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["ollama_base_url"] == "http://ollama.local:11434"
    assert body["ollama_model"] == "llama3.1"
    # the key itself is never echoed back, only whether one is set
    assert "ollama_api_key" not in body
    assert body["ollama_api_key_set"] is True
    assert body["ai_review_concurrency"] == 3
    assert body["ollama_log_requests"] is True

    cleared = await client.patch("/api/admin/settings", json={"ollama_api_key": ""})
    assert cleared.json()["ollama_api_key_set"] is False


async def test_ai_review_concurrency_must_be_positive(client, db_session):
    await _make_superuser(client, db_session, "admin6@example.com")
    resp = await client.patch("/api/admin/settings", json={"ai_review_concurrency": 0})
    assert resp.status_code == 400
