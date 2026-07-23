from tests.conftest import register_and_login


async def test_create_case_makes_creator_admin(client):
    await register_and_login(client, "admin@example.com")

    resp = await client.post("/api/cases", json={"name": "Smith v. Jones", "description": "x"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["my_role"] == "admin"

    listed = await client.get("/api/cases")
    assert listed.status_code == 200
    assert len(listed.json()) == 1


async def test_non_member_cannot_access_case(client):
    admin = await register_and_login(client, "admin2@example.com")
    resp = await client.post("/api/cases", json={"name": "Case A"})
    case_id = resp.json()["id"]

    # switch to a second user with a fresh client-side cookie jar
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as other_client:
        await register_and_login(other_client, "outsider@example.com")
        resp = await other_client.get(f"/api/cases/{case_id}")
        assert resp.status_code == 403

    assert admin["email"] == "admin2@example.com"


async def test_admin_can_add_member_and_reviewer_gains_access(client):
    await register_and_login(client, "admin3@example.com")
    resp = await client.post("/api/cases", json={"name": "Case B"})
    case_id = resp.json()["id"]

    from httpx import ASGITransport, AsyncClient

    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as reviewer_client:
        reviewer = await register_and_login(reviewer_client, "reviewer3@example.com")

        # not yet a member
        denied = await reviewer_client.get(f"/api/cases/{case_id}")
        assert denied.status_code == 403

        add_resp = await client.post(
            f"/api/cases/{case_id}/members",
            json={"email": "reviewer3@example.com", "role": "reviewer"},
        )
        assert add_resp.status_code == 201
        assert add_resp.json()["email"] == "reviewer3@example.com"
        assert add_resp.json()["user_id"] == reviewer["id"]

        allowed = await reviewer_client.get(f"/api/cases/{case_id}")
        assert allowed.status_code == 200
        assert allowed.json()["my_role"] == "reviewer"

        members = await client.get(f"/api/cases/{case_id}/members")
        assert members.status_code == 200
        emails = {m["email"] for m in members.json()}
        assert "admin3@example.com" in emails
        assert "reviewer3@example.com" in emails

        # reviewers cannot manage members
        forbidden = await reviewer_client.post(
            f"/api/cases/{case_id}/members",
            json={"email": "reviewer3@example.com", "role": "admin"},
        )
        assert forbidden.status_code == 403


async def test_add_member_with_unknown_email_returns_404(client):
    await register_and_login(client, "admin5@example.com")
    resp = await client.post("/api/cases", json={"name": "Case D"})
    case_id = resp.json()["id"]

    add_resp = await client.post(
        f"/api/cases/{case_id}/members",
        json={"email": "nobody@example.com", "role": "reviewer"},
    )
    assert add_resp.status_code == 404


async def test_case_stats_reflects_custodians_and_review_sets(client):
    await register_and_login(client, "admin6@example.com")
    resp = await client.post("/api/cases", json={"name": "Case E"})
    case_id = resp.json()["id"]

    await client.post(f"/api/cases/{case_id}/custodians", json={"name": "John Smith"})
    await client.post(f"/api/cases/{case_id}/review-sets", json={"name": "First pass"})

    stats = await client.get(f"/api/cases/{case_id}/stats")
    assert stats.status_code == 200
    body = stats.json()
    assert body["custodians_count"] == 1
    assert body["review_sets_count"] == 1
    assert body["documents_total"] == 0
    assert body["import_jobs_total"] == 0


async def test_custodian_crud_and_role_boundary(client):
    await register_and_login(client, "admin4@example.com")
    resp = await client.post("/api/cases", json={"name": "Case C"})
    case_id = resp.json()["id"]

    create = await client.post(
        f"/api/cases/{case_id}/custodians", json={"name": "John Smith", "email": "js@example.com"}
    )
    assert create.status_code == 201

    listed = await client.get(f"/api/cases/{case_id}/custodians")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
