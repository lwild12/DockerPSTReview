import uuid

from app.models.ai_review import AiRelevanceStatus, DocumentAiRelevance
from app.models.document import DedupStatus, DocType, Document
from app.models.system_settings import SystemSettings
from tests.conftest import register_and_login


async def _setup_case(client):
    await register_and_login(client, "admin@example.com")
    case_resp = await client.post("/api/cases", json={"name": "Case A"})
    return case_resp.json()["id"]


async def _seed_document(db_session, case_id) -> Document:
    document = Document(
        id=uuid.uuid4(),
        case_id=uuid.UUID(case_id),
        doc_type=DocType.email,
        dedup_status=DedupStatus.primary,
        subject="Q3 numbers",
        sender="a@x.com",
        recipients_to=["b@x.com"],
        body_text="hello",
        content_hash=str(uuid.uuid4()),
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)
    return document


async def test_get_summary_on_empty_case(client):
    case_id = await _setup_case(client)
    resp = await client.get(f"/api/cases/{case_id}/ai-review")
    assert resp.status_code == 200
    body = resp.json()
    assert body["criteria"] == ""
    assert body["candidate_count"] == 0
    assert body["ollama_configured"] is False


async def test_get_summary_reports_candidate_and_status_counts(client, db_session):
    case_id = await _setup_case(client)
    doc1 = await _seed_document(db_session, case_id)
    await _seed_document(db_session, case_id)

    db_session.add(
        DocumentAiRelevance(
            document_id=doc1.id, status=AiRelevanceStatus.completed, score=80, rationale="x"
        )
    )
    await db_session.commit()

    resp = await client.get(f"/api/cases/{case_id}/ai-review")
    body = resp.json()
    assert body["candidate_count"] == 2
    assert body["completed_count"] == 1
    assert body["unscored_count"] == 1


async def test_update_criteria(client):
    case_id = await _setup_case(client)
    resp = await client.patch(
        f"/api/cases/{case_id}/ai-review/criteria", json={"criteria": "Discusses layoffs"}
    )
    assert resp.status_code == 200
    assert resp.json()["criteria"] == "Discusses layoffs"

    follow_up = await client.get(f"/api/cases/{case_id}/ai-review")
    assert follow_up.json()["criteria"] == "Discusses layoffs"


async def test_run_requires_ollama_to_be_configured(client):
    case_id = await _setup_case(client)
    resp = await client.post(f"/api/cases/{case_id}/ai-review/run", json={})
    assert resp.status_code == 400
    assert "not configured" in resp.json()["detail"]


async def test_run_dispatches_when_ollama_is_configured(client, db_session, monkeypatch):
    case_id = await _setup_case(client)
    await _seed_document(db_session, case_id)
    db_session.add(
        SystemSettings(ollama_base_url="http://ollama.local:11434", ollama_model="llama3.1")
    )
    await db_session.commit()

    dispatched = {}

    def _fake_delay(case_id_arg, rescore_all=False):
        dispatched["case_id"] = case_id_arg
        dispatched["rescore_all"] = rescore_all

    from app.api.routers import ai_review as ai_review_router

    monkeypatch.setattr(ai_review_router.run_ai_review_task, "delay", _fake_delay)

    resp = await client.post(f"/api/cases/{case_id}/ai-review/run", json={"rescore_all": True})
    assert resp.status_code == 200
    assert dispatched == {"case_id": case_id, "rescore_all": True}


async def test_non_member_cannot_view_summary(client):
    case_id = await _setup_case(client)
    await register_and_login(client, "outsider@example.com")

    resp = await client.get(f"/api/cases/{case_id}/ai-review")
    assert resp.status_code == 403


async def test_reviewer_cannot_trigger_run(client):
    case_id = await _setup_case(client)

    # Register the future reviewer under a separate throwaway client so
    # registering them doesn't change *this* client's logged-in session
    # (still the admin who created the case).
    from httpx import ASGITransport
    from httpx import AsyncClient as _AsyncClient

    from app.main import app

    async with _AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as other:
        await register_and_login(other, "reviewer@example.com")

    add_resp = await client.post(
        f"/api/cases/{case_id}/members", json={"email": "reviewer@example.com", "role": "reviewer"}
    )
    assert add_resp.status_code == 201

    await register_and_login(client, "reviewer@example.com")
    resp = await client.post(f"/api/cases/{case_id}/ai-review/run", json={})
    assert resp.status_code == 403
