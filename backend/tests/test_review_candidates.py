import uuid

from app.models.document import DedupStatus, DocType, Document, NearDuplicateCluster
from app.services.review_candidates import get_review_candidate_document_ids
from tests.conftest import register_and_login


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
        sender="a@x.com",
        recipients_to=["b@x.com"],
        body_text="hello",
        content_hash=str(uuid.uuid4()),
    )
    defaults.update(overrides)
    document = Document(**defaults)
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)
    return document


async def test_empty_case_returns_no_candidates(client, db_session):
    _, case_id = await _setup_case(client)
    candidates = await get_review_candidate_document_ids(uuid.UUID(case_id), db_session)
    assert candidates == []


async def test_excludes_duplicates(client, db_session):
    _, case_id = await _setup_case(client)
    primary = await _seed_document(db_session, case_id, dedup_status=DedupStatus.primary)
    await _seed_document(
        db_session, case_id, dedup_status=DedupStatus.duplicate, duplicate_of_id=primary.id
    )

    candidates = await get_review_candidate_document_ids(uuid.UUID(case_id), db_session)
    assert candidates == [primary.id]


async def test_excludes_redundant_thread_messages(client, db_session):
    _, case_id = await _setup_case(client)
    inclusive = await _seed_document(
        db_session, case_id, doc_type=DocType.email, is_inclusive_email=True
    )
    await _seed_document(db_session, case_id, doc_type=DocType.email, is_inclusive_email=False)

    candidates = await get_review_candidate_document_ids(uuid.UUID(case_id), db_session)
    assert candidates == [inclusive.id]


async def test_is_inclusive_email_flag_is_ignored_for_non_email_doc_types(client, db_session):
    # is_inclusive_email is an email-threading concept -- an attachment
    # flagged False (however that happened) shouldn't be excluded by it.
    _, case_id = await _setup_case(client)
    attachment = await _seed_document(
        db_session, case_id, doc_type=DocType.attachment, is_inclusive_email=False
    )

    candidates = await get_review_candidate_document_ids(uuid.UUID(case_id), db_session)
    assert candidates == [attachment.id]


async def test_near_duplicate_cluster_collapses_to_one_representative(client, db_session):
    _, case_id = await _setup_case(client)
    cluster_id = uuid.uuid4()
    db_session.add(NearDuplicateCluster(id=cluster_id, case_id=uuid.UUID(case_id)))
    await db_session.commit()

    doc1 = await _seed_document(db_session, case_id, near_duplicate_cluster_id=cluster_id)
    doc2 = await _seed_document(db_session, case_id, near_duplicate_cluster_id=cluster_id)
    unclustered = await _seed_document(db_session, case_id)

    candidates = await get_review_candidate_document_ids(uuid.UUID(case_id), db_session)
    clustered_survivors = [c for c in candidates if c in (doc1.id, doc2.id)]
    assert len(clustered_survivors) == 1
    assert unclustered.id in candidates
    assert len(candidates) == 2


async def test_documents_from_other_cases_never_appear(client, db_session):
    _, case_id = await _setup_case(client)
    _, other_case_id = await _setup_case(client)
    await _seed_document(db_session, other_case_id)

    candidates = await get_review_candidate_document_ids(uuid.UUID(case_id), db_session)
    assert candidates == []
