import uuid

from app.models.document import DocType, Document
from tests.conftest import register_and_login


async def _setup_case(client):
    await register_and_login(client, "admin@example.com")
    case_resp = await client.post("/api/cases", json={"name": "Search Case"})
    return case_resp.json()["id"]


async def _seed_document(db_session, case_id, **overrides) -> Document:
    defaults = dict(
        id=uuid.uuid4(),
        case_id=uuid.UUID(case_id),
        doc_type=DocType.email,
        subject="",
        sender="",
        body_text="",
        content_hash=str(uuid.uuid4()),
    )
    defaults.update(overrides)
    document = Document(**defaults)
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)
    return document


async def test_full_text_search_matches_stemmed_word_forms(client, db_session):
    # "budgets" (plural) should match a document whose subject only contains
    # "budget" via Postgres's tsvector stemming -- a plain ILIKE '%budgets%'
    # would NOT match "Budget report", so this proves the tsvector path (not
    # just the ILIKE fallback) is doing real work.
    case_id = await _setup_case(client)
    await _seed_document(db_session, case_id, subject="Budget report")
    await _seed_document(db_session, case_id, subject="Unrelated memo")

    resp = await client.get(f"/api/cases/{case_id}/documents", params={"q": "budgets"})
    assert resp.status_code == 200
    subjects = [d["subject"] for d in resp.json()]
    assert subjects == ["Budget report"]


async def test_full_text_search_covers_body_text(client, db_session):
    case_id = await _setup_case(client)
    await _seed_document(
        db_session, case_id, subject="Re: catch up", body_text="Let's discuss the merger terms."
    )
    await _seed_document(db_session, case_id, subject="Lunch", body_text="Sandwiches at noon.")

    resp = await client.get(f"/api/cases/{case_id}/documents", params={"q": "merger"})
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["subject"] == "Re: catch up"


async def test_full_text_search_ranks_stronger_matches_first(client, db_session):
    case_id = await _setup_case(client)
    weak = await _seed_document(
        db_session, case_id, subject="Weekly notes", body_text="One mention of contract here."
    )
    strong = await _seed_document(
        db_session,
        case_id,
        subject="Contract contract contract",
        body_text="This contract is about a contract renewal contract.",
    )

    resp = await client.get(f"/api/cases/{case_id}/documents", params={"q": "contract"})
    assert resp.status_code == 200
    ids = [d["id"] for d in resp.json()]
    assert ids == [str(strong.id), str(weak.id)]


async def test_search_falls_back_to_substring_for_non_word_queries(client, db_session):
    # A partial-word/substring query that tsvector stemming wouldn't match on
    # its own should still be caught by the ILIKE fallback.
    case_id = await _setup_case(client)
    await _seed_document(db_session, case_id, subject="Q3-BUDG-2026 draft")
    await _seed_document(db_session, case_id, subject="Something else")

    resp = await client.get(f"/api/cases/{case_id}/documents", params={"q": "BUDG"})
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["subject"] == "Q3-BUDG-2026 draft"
