async def test_healthz(client):
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_api_docs_disabled_by_default(client):
    # Regression guard: once a real Register page exists there's no reason
    # to leave every endpoint publicly browsable/callable via Swagger.
    assert (await client.get("/docs")).status_code == 404
    assert (await client.get("/redoc")).status_code == 404
    assert (await client.get("/openapi.json")).status_code == 404


async def test_api_docs_can_be_enabled_live_via_admin_settings(client, db_session):
    import uuid

    from sqlalchemy import select

    from app.models.user import User
    from tests.conftest import register_and_login

    me = await register_and_login(client, "docsadmin@example.com")
    result = await db_session.execute(select(User).where(User.id == uuid.UUID(me["id"])))
    user = result.scalar_one()
    user.is_superuser = True
    await db_session.commit()

    assert (await client.get("/docs")).status_code == 404

    updated = await client.patch("/api/admin/settings", json={"enable_api_docs": True})
    assert updated.status_code == 200

    # No restart needed -- the gate reads the live DB row on every request.
    assert (await client.get("/docs")).status_code == 200
    assert (await client.get("/openapi.json")).status_code == 200
