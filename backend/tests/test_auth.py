from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.conftest import register_and_login


async def test_register_and_login(client):
    me = await register_and_login(client, "alice@example.com", full_name="Alice")
    assert me["email"] == "alice@example.com"
    assert me["full_name"] == "Alice"
    assert me["is_active"] is True


async def test_first_registered_user_becomes_superuser_subsequent_do_not(client, db_session):
    first = await register_and_login(client, "first@example.com")
    assert first["is_superuser"] is True

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as second_client:
        second = await register_and_login(second_client, "second@example.com")
        assert second["is_superuser"] is False


async def test_registration_enabled_defaults_to_true_and_can_be_disabled(client, db_session):
    public_before = await client.get("/api/auth/registration-enabled")
    assert public_before.status_code == 200
    assert public_before.json() == {"enabled": True}

    # first user always gets through, and becomes the admin who can toggle it
    await register_and_login(client, "admin@example.com")

    disable = await client.patch("/api/admin/settings", json={"registration_enabled": False})
    assert disable.status_code == 200
    assert disable.json()["registration_enabled"] is False

    public_after = await client.get("/api/auth/registration-enabled")
    assert public_after.json() == {"enabled": False}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as blocked_client:
        blocked = await blocked_client.post(
            "/api/auth/register",
            json={"email": "blocked@example.com", "password": "SuperSecret123!"},
        )
        assert blocked.status_code == 403

    reenable = await client.patch("/api/admin/settings", json={"registration_enabled": True})
    assert reenable.json()["registration_enabled"] is True

    async with AsyncClient(transport=transport, base_url="http://test") as allowed_client:
        allowed = await register_and_login(allowed_client, "allowed@example.com")
        assert allowed["is_superuser"] is False


async def test_cases_requires_auth(client):
    resp = await client.get("/api/cases")
    assert resp.status_code == 401


async def test_login_wrong_password(client):
    await client.post(
        "/api/auth/register",
        json={"email": "bob@example.com", "password": "SuperSecret123!"},
    )
    resp = await client.post(
        "/api/auth/login",
        data={"username": "bob@example.com", "password": "wrong-password"},
    )
    assert resp.status_code == 400
