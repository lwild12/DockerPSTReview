import uuid

from sqlalchemy import select

from app.models.case import Case, CaseMembership, CaseRole
from app.models.document import DedupStatus, DocType, Document, NearDuplicateCluster, Thread
from app.models.user import User
from app.tasks.analytics_tasks import run_case_analytics

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


async def _make_case(db_session) -> Case:
    user = User(id=uuid.uuid4(), email=f"{uuid.uuid4()}@x.com", hashed_password="x", full_name="")
    db_session.add(user)
    await db_session.flush()

    case = Case(id=uuid.uuid4(), name="Test case", description="", created_by_id=user.id)
    db_session.add(case)
    membership = CaseMembership(
        id=uuid.uuid4(), case_id=case.id, user_id=user.id, role=CaseRole.admin
    )
    db_session.add(membership)
    await db_session.commit()
    return case


def _email(case_id, **kwargs) -> Document:
    defaults = {
        "id": uuid.uuid4(),
        "case_id": case_id,
        "doc_type": DocType.email,
        "dedup_status": DedupStatus.primary,
    }
    defaults.update(kwargs)
    return Document(**defaults)


async def test_marks_leaf_message_inclusive_and_ancestors_not(db_session):
    case = await _make_case(db_session)
    thread = Thread(id=uuid.uuid4(), case_id=case.id)
    db_session.add(thread)
    await db_session.flush()

    root = _email(
        case.id, thread_id=thread.id, message_id="<root@x>", subject="S", body_text="root"
    )
    reply = _email(
        case.id,
        thread_id=thread.id,
        message_id="<reply@x>",
        in_reply_to="<root@x>",
        references=["<root@x>"],
        subject="Re: S",
        body_text="reply",
    )
    db_session.add_all([root, reply])
    await db_session.commit()

    stats = await run_case_analytics(case.id, db_session)
    assert stats["non_inclusive_emails"] == 1

    await db_session.refresh(root)
    await db_session.refresh(reply)
    assert root.is_inclusive_email is False
    assert reply.is_inclusive_email is True


async def test_duplicate_status_documents_are_excluded(db_session):
    case = await _make_case(db_session)
    thread = Thread(id=uuid.uuid4(), case_id=case.id)
    db_session.add(thread)
    await db_session.flush()

    root = _email(
        case.id, thread_id=thread.id, message_id="<root@x>", subject="S", body_text="root"
    )
    dup_reply = _email(
        case.id,
        thread_id=thread.id,
        message_id="<reply@x>",
        in_reply_to="<root@x>",
        references=["<root@x>"],
        subject="Re: S",
        body_text="reply",
        dedup_status=DedupStatus.duplicate,
    )
    db_session.add_all([root, dup_reply])
    await db_session.commit()

    stats = await run_case_analytics(case.id, db_session)
    # the reply that would have superseded root is a duplicate and excluded,
    # so root has nothing referencing it among primary documents
    assert stats["non_inclusive_emails"] == 0
    await db_session.refresh(root)
    assert root.is_inclusive_email is True


async def test_near_duplicate_emails_are_clustered_and_stored(db_session):
    case = await _make_case(db_session)
    doc_a = _email(case.id, subject="A", body_text=LONG_BODY)
    doc_b = _email(
        case.id, subject="B", body_text=LONG_BODY.replace("Friday's", "Thursday's")
    )
    doc_c = _email(case.id, subject="C", body_text="Completely unrelated picnic plans.")
    db_session.add_all([doc_a, doc_b, doc_c])
    await db_session.commit()

    stats = await run_case_analytics(case.id, db_session)
    assert stats["near_duplicate_clusters"] == 1

    await db_session.refresh(doc_a)
    await db_session.refresh(doc_b)
    await db_session.refresh(doc_c)
    assert doc_a.near_duplicate_cluster_id is not None
    assert doc_a.near_duplicate_cluster_id == doc_b.near_duplicate_cluster_id
    assert doc_c.near_duplicate_cluster_id is None

    result = await db_session.execute(
        select(NearDuplicateCluster).where(NearDuplicateCluster.case_id == case.id)
    )
    assert len(result.scalars().all()) == 1


async def test_recompute_clears_stale_clusters(db_session):
    case = await _make_case(db_session)
    doc_a = _email(case.id, subject="A", body_text=LONG_BODY)
    doc_b = _email(
        case.id, subject="B", body_text=LONG_BODY.replace("Friday's", "Thursday's")
    )
    db_session.add_all([doc_a, doc_b])
    await db_session.commit()

    await run_case_analytics(case.id, db_session)

    # rewrite doc_b so it no longer resembles doc_a
    doc_b.body_text = "Something else entirely, unrelated to the first message."
    await db_session.commit()

    stats = await run_case_analytics(case.id, db_session)
    assert stats["near_duplicate_clusters"] == 0

    result = await db_session.execute(
        select(NearDuplicateCluster).where(NearDuplicateCluster.case_id == case.id)
    )
    assert result.scalars().all() == []

    await db_session.refresh(doc_a)
    assert doc_a.near_duplicate_cluster_id is None


async def test_unknown_case_is_a_no_op(db_session):
    stats = await run_case_analytics(uuid.uuid4(), db_session)
    assert stats == {"near_duplicate_clusters": 0, "non_inclusive_emails": 0}
