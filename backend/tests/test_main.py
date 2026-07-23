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
