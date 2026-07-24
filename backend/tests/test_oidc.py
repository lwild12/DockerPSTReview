import uuid

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

import app.api.routers.oidc as oidc_module
import app.services.encryption as encryption_module
from app.models.user import User
from tests.conftest import register_and_login


@pytest.fixture
def encryption_key(monkeypatch):
    key = Fernet.generate_key().decode()

    class FakeSettings:
        secret_encryption_key = key

    monkeypatch.setattr(encryption_module, "get_settings", lambda: FakeSettings())
    return key


async def _make_superuser(client, db_session, email: str) -> dict:
    me = await register_and_login(client, email)
    result = await db_session.execute(select(User).where(User.id == uuid.UUID(me["id"])))
    user = result.scalar_one()
    user.is_superuser = True
    await db_session.commit()
    return me


async def _configure_oidc(client, db_session, admin_email: str, encryption_key):
    await _make_superuser(client, db_session, admin_email)
    resp = await client.patch(
        "/api/admin/settings",
        json={
            "oidc_issuer_url": "https://idp.example.com",
            "oidc_client_id": "client-123",
            "oidc_client_secret": "super-secret",
            "oidc_display_name": "Example SSO",
        },
    )
    assert resp.status_code == 200
    enabled = await client.patch("/api/admin/settings", json={"oidc_enabled": True})
    assert enabled.status_code == 200
    assert enabled.json()["oidc_enabled"] is True


async def test_oidc_config_disabled_by_default(client):
    resp = await client.get("/api/auth/oidc/config")
    assert resp.status_code == 200
    assert resp.json() == {"enabled": False}


async def test_enabling_oidc_without_full_config_fails(client, db_session):
    await _make_superuser(client, db_session, "admin@example.com")
    resp = await client.patch("/api/admin/settings", json={"oidc_enabled": True})
    assert resp.status_code == 400


async def test_configuring_and_enabling_oidc_never_exposes_the_secret(
    client, db_session, encryption_key
):
    await _configure_oidc(client, db_session, "admin@example.com", encryption_key)

    settings_resp = await client.get("/api/admin/settings")
    body = settings_resp.json()
    assert body["oidc_client_secret_set"] is True
    assert "oidc_client_secret" not in body
    assert "super-secret" not in settings_resp.text

    public = await client.get("/api/auth/oidc/config")
    assert public.json() == {"enabled": True, "display_name": "Example SSO"}


async def test_oidc_login_returns_a_clean_error_when_issuer_is_unreachable(
    client, db_session, encryption_key, monkeypatch
):
    await _configure_oidc(client, db_session, "admin@example.com", encryption_key)

    class _UnreachableAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, headers=None):
            raise oidc_module.httpx.ConnectError("connection refused")

    monkeypatch.setattr(oidc_module.httpx, "AsyncClient", lambda **kw: _UnreachableAsyncClient())

    resp = await client.get("/api/auth/oidc/login", follow_redirects=False)
    assert resp.status_code == 502


async def test_oidc_login_redirects_to_discovered_authorization_endpoint(
    client, db_session, encryption_key, monkeypatch
):
    await _configure_oidc(client, db_session, "admin@example.com", encryption_key)

    async def fake_discover(issuer_url):
        assert issuer_url == "https://idp.example.com"
        return {"authorization_endpoint": "https://idp.example.com/authorize"}

    monkeypatch.setattr(oidc_module, "_discover", fake_discover)

    resp = await client.get("/api/auth/oidc/login", follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers["location"].startswith("https://idp.example.com/authorize?")
    assert "state=" in resp.headers["location"]
    assert "oidc_state" in resp.cookies


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class _FakeAsyncClient:
    def __init__(self, token_payload, userinfo_payload, token_status=200, userinfo_status=200):
        self._token_payload = token_payload
        self._userinfo_payload = userinfo_payload
        self._token_status = token_status
        self._userinfo_status = userinfo_status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, data=None):
        return _FakeResponse(self._token_status, self._token_payload)

    async def get(self, url, headers=None):
        return _FakeResponse(self._userinfo_status, self._userinfo_payload)


async def test_oidc_callback_creates_and_logs_in_a_new_user(
    client, db_session, encryption_key, monkeypatch
):
    await _configure_oidc(client, db_session, "admin@example.com", encryption_key)

    async def fake_discover(issuer_url):
        return {
            "authorization_endpoint": "https://idp.example.com/authorize",
            "token_endpoint": "https://idp.example.com/token",
            "userinfo_endpoint": "https://idp.example.com/userinfo",
        }

    monkeypatch.setattr(oidc_module, "_discover", fake_discover)
    monkeypatch.setattr(
        oidc_module.httpx,
        "AsyncClient",
        lambda **kw: _FakeAsyncClient(
            token_payload={"access_token": "fake-access-token"},
            userinfo_payload={"email": "newuser@example.com", "name": "New User"},
        ),
    )

    login_resp = await client.get("/api/auth/oidc/login", follow_redirects=False)
    state = login_resp.headers["location"].split("state=")[1].split("&")[0]

    callback_resp = await client.get(
        f"/api/auth/oidc/callback?code=abc&state={state}", follow_redirects=False
    )
    assert callback_resp.status_code == 307
    assert callback_resp.headers["location"].endswith("/cases")
    assert "pstreview_auth" in callback_resp.cookies

    result = await db_session.execute(select(User).where(User.email == "newuser@example.com"))
    user = result.scalar_one()
    assert user.full_name == "New User"
    assert user.is_active is True
    assert user.is_verified is True
    assert user.is_superuser is False


async def test_oidc_callback_rejects_mismatched_state(
    client, db_session, encryption_key, monkeypatch
):
    await _configure_oidc(client, db_session, "admin@example.com", encryption_key)

    async def fake_discover(issuer_url):
        return {"authorization_endpoint": "https://idp.example.com/authorize"}

    monkeypatch.setattr(oidc_module, "_discover", fake_discover)

    await client.get("/api/auth/oidc/login", follow_redirects=False)
    resp = await client.get(
        "/api/auth/oidc/callback?code=abc&state=not-the-real-state", follow_redirects=False
    )
    assert resp.status_code == 400


async def test_oidc_callback_rejects_deactivated_existing_user(
    client, db_session, encryption_key, monkeypatch
):
    await _configure_oidc(client, db_session, "admin@example.com", encryption_key)

    result = await db_session.execute(select(User).where(User.email == "admin@example.com"))
    admin_user = result.scalar_one()
    admin_user.is_active = False
    await db_session.commit()

    async def fake_discover(issuer_url):
        return {
            "authorization_endpoint": "https://idp.example.com/authorize",
            "token_endpoint": "https://idp.example.com/token",
            "userinfo_endpoint": "https://idp.example.com/userinfo",
        }

    monkeypatch.setattr(oidc_module, "_discover", fake_discover)
    monkeypatch.setattr(
        oidc_module.httpx,
        "AsyncClient",
        lambda **kw: _FakeAsyncClient(
            token_payload={"access_token": "fake-access-token"},
            userinfo_payload={"email": "admin@example.com", "name": "Admin"},
        ),
    )

    login_resp = await client.get("/api/auth/oidc/login", follow_redirects=False)
    state = login_resp.headers["location"].split("state=")[1].split("&")[0]

    resp = await client.get(
        f"/api/auth/oidc/callback?code=abc&state={state}", follow_redirects=False
    )
    assert resp.status_code == 403
