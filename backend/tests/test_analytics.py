import uuid

from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.document import DedupStatus, DocType, Document
from tests.conftest import register_and_login

LONG_BODY = (
    "Please review the attached quarterly budget proposal before Friday's meeting "
    "and send any comments to the finance team as soon as possible so we can "
    "finalize the numbers ahead of the board presentation next week. This draft "
    "reflects the updated hiring plan and the revised marketing spend we discussed "
    "on the call yesterday, along with the vendor contract renewals due next month "
    "and the office lease renegotiation the facilities team has been tracking since "
    "the start of the quarter, so please flag anything that looks off before we "
    "circulate this more broadly to the rest of the leadership team on Monday."
)


async def _setup_case(client):
    admin = await register_and_login(client, "admin@example.com")
    case_resp = await client.post("/api/cases", json={"name": "Case A"})
    case_id = case_resp.json()["id"]
    return admin, case_id


async def _seed_document(db_session, case_id, **overrides) -> Document:
    defaults = dict(
        id=uuid.uuid4(),
        case_id=uuid.UUID(case_id),
        doc_type=DocType.email,
        subject="Test subject",
        body_text="hello",
        content_hash=str(uuid.uuid4()),
        dedup_status=DedupStatus.primary,
    )
    defaults.update(overrides)
    document = Document(**defaults)
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)
    return document


async def test_analytics_summary_before_any_recompute(client, db_session):
    _, case_id = await _setup_case(client)
    resp = await client.get(f"/api/cases/{case_id}/analytics")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "computed_at": None,
        "near_duplicate_cluster_count": 0,
        "non_inclusive_email_count": 0,
    }


async def test_recompute_clusters_near_duplicates_and_updates_summary(client, db_session):
    _, case_id = await _setup_case(client)
    doc_a = await _seed_document(db_session, case_id, subject="A", body_text=LONG_BODY)
    doc_b = await _seed_document(
        db_session, case_id, subject="B", body_text=LONG_BODY.replace("Friday's", "Thursday's")
    )

    resp = await client.post(f"/api/cases/{case_id}/analytics/recompute")
    assert resp.status_code == 200
    body = resp.json()
    assert body["computed_at"] is not None
    assert body["near_duplicate_cluster_count"] == 1

    summary = await client.get(f"/api/cases/{case_id}/analytics")
    assert summary.json()["near_duplicate_cluster_count"] == 1

    clusters = await client.get(f"/api/cases/{case_id}/near-duplicate-clusters")
    assert clusters.status_code == 200
    assert len(clusters.json()) == 1
    cluster_id = clusters.json()[0]["id"]
    assert clusters.json()[0]["member_count"] == 2

    members = await client.get(
        f"/api/cases/{case_id}/near-duplicate-clusters/{cluster_id}/documents"
    )
    assert members.status_code == 200
    member_ids = {d["id"] for d in members.json()}
    assert member_ids == {str(doc_a.id), str(doc_b.id)}


async def test_document_list_filters_by_inclusiveness_and_cluster(client, db_session):
    _, case_id = await _setup_case(client)
    await _seed_document(db_session, case_id, subject="A", body_text=LONG_BODY)
    await _seed_document(
        db_session, case_id, subject="B", body_text=LONG_BODY.replace("Friday's", "Thursday's")
    )
    await client.post(f"/api/cases/{case_id}/analytics/recompute")

    inclusive_only = await client.get(
        f"/api/cases/{case_id}/documents", params={"is_inclusive_email": "true"}
    )
    assert len(inclusive_only.json()) == 2  # neither is part of a reply thread

    clusters = await client.get(f"/api/cases/{case_id}/near-duplicate-clusters")
    cluster_id = clusters.json()[0]["id"]
    by_cluster = await client.get(
        f"/api/cases/{case_id}/documents", params={"near_duplicate_cluster_id": cluster_id}
    )
    assert len(by_cluster.json()) == 2


async def test_near_duplicate_cluster_documents_missing_cluster_returns_404(client, db_session):
    _, case_id = await _setup_case(client)
    resp = await client.get(
        f"/api/cases/{case_id}/near-duplicate-clusters/{uuid.uuid4()}/documents"
    )
    assert resp.status_code == 404


async def test_reviewer_cannot_recompute_but_can_view_summary(client, db_session):
    _, case_id = await _setup_case(client)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as reviewer_client:
        reviewer = await register_and_login(reviewer_client, "reviewer@example.com")
        await client.post(
            f"/api/cases/{case_id}/members",
            json={"email": reviewer["email"], "role": "reviewer"},
        )

        forbidden = await reviewer_client.post(f"/api/cases/{case_id}/analytics/recompute")
        assert forbidden.status_code == 403

        allowed = await reviewer_client.get(f"/api/cases/{case_id}/analytics")
        assert allowed.status_code == 200
