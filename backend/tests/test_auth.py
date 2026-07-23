from tests.conftest import register_and_login


async def test_register_and_login(client):
    me = await register_and_login(client, "alice@example.com", full_name="Alice")
    assert me["email"] == "alice@example.com"
    assert me["full_name"] == "Alice"
    assert me["is_active"] is True


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
