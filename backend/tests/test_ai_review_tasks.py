import threading
import uuid

from app.models.ai_review import AiRelevanceStatus, DocumentAiRelevance
from app.models.case import Case
from app.models.document import DedupStatus, DocType, Document
from app.models.system_settings import SystemSettings
from app.models.user import User
from app.services.ollama_client import OllamaError, RelevanceResult
from app.tasks import ai_review_tasks


async def _make_case(db_session, **overrides) -> Case:
    user = User(id=uuid.uuid4(), email=f"{uuid.uuid4()}@x.com", hashed_password="x", full_name="")
    db_session.add(user)
    await db_session.flush()

    defaults = dict(
        id=uuid.uuid4(),
        name="AI review case",
        description="",
        created_by_id=user.id,
        ai_review_criteria="Discussions of the Q3 budget",
    )
    defaults.update(overrides)
    case = Case(**defaults)
    db_session.add(case)
    await db_session.commit()
    return case


async def _seed_documents(db_session, case_id, count) -> list[Document]:
    documents = [
        Document(
            id=uuid.uuid4(),
            case_id=case_id,
            doc_type=DocType.email,
            dedup_status=DedupStatus.primary,
            subject=f"Doc {i}",
            sender="a@x.com",
            recipients_to=["b@x.com"],
            body_text="hello",
            content_hash=str(uuid.uuid4()),
        )
        for i in range(count)
    ]
    db_session.add_all(documents)
    await db_session.commit()
    return documents


def test_plain_text_from_html_strips_tags_and_separates_blocks():
    html_body = (
        "<html><body><p>Hello <b>world</b></p><script>evil()</script>"
        "<p>Second &amp; para</p></body></html>"
    )
    text = ai_review_tasks._plain_text_from_html(html_body)
    assert "evil()" not in text
    assert "Hello world" in text
    assert "Second & para" in text
    # block boundary preserved -- the two paragraphs don't run together
    assert "worldSecond" not in text


def test_text_for_scoring_prefers_body_text_when_present():
    document = Document(
        id=uuid.uuid4(),
        case_id=uuid.uuid4(),
        doc_type=DocType.email,
        body_text="Plain text body.",
        body_html="<p>HTML body.</p>",
    )
    assert ai_review_tasks._text_for_scoring(document) == "Plain text body."


def test_text_for_scoring_falls_back_to_html_when_body_text_empty():
    # The actual production bug: an HTML-only email (no text/plain MIME
    # part at all, common for templated corporate mail) left body_text
    # empty, so the model only ever saw subject/sender -- confirmed by a
    # live rationale that said as much.
    document = Document(
        id=uuid.uuid4(),
        case_id=uuid.uuid4(),
        doc_type=DocType.email,
        body_text="",
        body_html="<p>Only available as HTML.</p>",
    )
    assert "Only available as HTML." in ai_review_tasks._text_for_scoring(document)


def test_text_for_scoring_falls_back_to_html_when_body_text_is_whitespace_only():
    # A real email observed in production had a text/plain MIME part
    # containing only "\n" -- a near-empty placeholder some mail clients
    # write alongside the real HTML-formatted content. That string is
    # non-empty, so a plain `if document.body_text:` took it and never
    # fell back to body_html, sending the model 1 character of body text
    # (confirmed via the new request-preview log line) for a message with
    # a full, substantial HTML body.
    document = Document(
        id=uuid.uuid4(),
        case_id=uuid.uuid4(),
        doc_type=DocType.email,
        body_text="\n",
        body_html="<p>The real content is only here.</p>",
    )
    assert "The real content is only here." in ai_review_tasks._text_for_scoring(document)


def test_text_for_scoring_includes_ocr_text():
    document = Document(
        id=uuid.uuid4(),
        case_id=uuid.uuid4(),
        doc_type=DocType.attachment,
        body_text="",
        body_html="",
        ocr_text="Scanned page content.",
    )
    assert "Scanned page content." in ai_review_tasks._text_for_scoring(document)


async def test_run_ai_review_sends_html_derived_text_for_html_only_emails(db_session, monkeypatch):
    db_session.add(SystemSettings(ai_review_concurrency=1))
    await db_session.commit()

    case = await _make_case(db_session)
    document = Document(
        id=uuid.uuid4(),
        case_id=case.id,
        doc_type=DocType.email,
        dedup_status=DedupStatus.primary,
        subject="Account Security Best Practices",
        sender="spam@clf.uk",
        recipients_to=[],
        body_text="",
        body_html="<p>Never share your password with anyone.</p>",
        content_hash=str(uuid.uuid4()),
    )
    db_session.add(document)
    await db_session.commit()

    seen_bodies = []

    async def _fake_score(*, body, **kwargs):
        seen_bodies.append(body)
        return RelevanceResult(score=10, rationale="x")

    monkeypatch.setattr(ai_review_tasks, "score_document_relevance", _fake_score)

    await ai_review_tasks.run_ai_review(case.id, db_session)

    assert len(seen_bodies) == 1
    assert "Never share your password with anyone." in seen_bodies[0]


async def test_run_ai_review_scores_all_candidates_and_sets_run_timestamps(db_session, monkeypatch):
    db_session.add(SystemSettings(ai_review_concurrency=2))
    await db_session.commit()

    case = await _make_case(db_session)
    documents = await _seed_documents(db_session, case.id, 3)

    async def _fake_score(**kwargs):
        return RelevanceResult(score=75, rationale="Looks relevant.")

    monkeypatch.setattr(ai_review_tasks, "score_document_relevance", _fake_score)

    await ai_review_tasks.run_ai_review(case.id, db_session)

    await db_session.refresh(case)
    assert case.ai_review_last_run_started_at is not None
    assert case.ai_review_last_run_completed_at is not None

    for document in documents:
        await db_session.refresh(document, attribute_names=["ai_relevance"])
        relevance = document.ai_relevance
        assert relevance is not None
        assert relevance.status == AiRelevanceStatus.completed
        assert relevance.score == 75
        assert relevance.rationale == "Looks relevant."
        assert relevance.criteria_snapshot == case.ai_review_criteria


async def test_run_ai_review_marks_ollama_failures_without_losing_other_documents(
    db_session, monkeypatch
):
    db_session.add(SystemSettings(ai_review_concurrency=2))
    await db_session.commit()

    case = await _make_case(db_session)
    documents = await _seed_documents(db_session, case.id, 2)
    failing_id = documents[0].id

    async def _fake_score(*, subject, **kwargs):
        if subject == documents[0].subject:
            raise OllamaError("model timed out")
        return RelevanceResult(score=40, rationale="Somewhat relevant.")

    monkeypatch.setattr(ai_review_tasks, "score_document_relevance", _fake_score)

    await ai_review_tasks.run_ai_review(case.id, db_session)

    for document in documents:
        await db_session.refresh(document, attribute_names=["ai_relevance"])
        relevance = document.ai_relevance
        if document.id == failing_id:
            assert relevance.status == AiRelevanceStatus.failed
            assert "model timed out" in relevance.error
        else:
            assert relevance.status == AiRelevanceStatus.completed
            assert relevance.score == 40


async def test_run_ai_review_respects_concurrency_setting(db_session, monkeypatch):
    db_session.add(SystemSettings(ai_review_concurrency=2))
    await db_session.commit()

    case = await _make_case(db_session)
    await _seed_documents(db_session, case.id, 6)

    lock = threading.Lock()
    state = {"current": 0, "max": 0}

    async def _fake_score(**kwargs):
        with lock:
            state["current"] += 1
            state["max"] = max(state["max"], state["current"])
        import asyncio

        await asyncio.sleep(0.1)
        with lock:
            state["current"] -= 1
        return RelevanceResult(score=10, rationale="x")

    monkeypatch.setattr(ai_review_tasks, "score_document_relevance", _fake_score)

    await ai_review_tasks.run_ai_review(case.id, db_session)

    assert state["max"] >= 2
    assert state["max"] <= 2


async def test_run_ai_review_default_mode_skips_up_to_date_completed_scores(
    db_session, monkeypatch
):
    db_session.add(SystemSettings(ai_review_concurrency=1))
    await db_session.commit()

    case = await _make_case(db_session)
    documents = await _seed_documents(db_session, case.id, 2)

    db_session.add(
        DocumentAiRelevance(
            document_id=documents[0].id,
            status=AiRelevanceStatus.completed,
            score=99,
            rationale="Already scored.",
            criteria_snapshot=case.ai_review_criteria,
        )
    )
    await db_session.commit()

    scored_subjects = []

    async def _fake_score(*, subject, **kwargs):
        scored_subjects.append(subject)
        return RelevanceResult(score=50, rationale="Freshly scored.")

    monkeypatch.setattr(ai_review_tasks, "score_document_relevance", _fake_score)

    await ai_review_tasks.run_ai_review(case.id, db_session)

    assert documents[0].subject not in scored_subjects
    assert documents[1].subject in scored_subjects

    await db_session.refresh(documents[0], attribute_names=["ai_relevance"])
    assert documents[0].ai_relevance.score == 99


async def test_run_ai_review_default_mode_rescoring_a_failed_document(db_session, monkeypatch):
    db_session.add(SystemSettings(ai_review_concurrency=1))
    await db_session.commit()

    case = await _make_case(db_session)
    documents = await _seed_documents(db_session, case.id, 1)

    db_session.add(
        DocumentAiRelevance(
            document_id=documents[0].id,
            status=AiRelevanceStatus.failed,
            error="previous failure",
            criteria_snapshot=case.ai_review_criteria,
        )
    )
    await db_session.commit()

    async def _fake_score(**kwargs):
        return RelevanceResult(score=60, rationale="Recovered.")

    monkeypatch.setattr(ai_review_tasks, "score_document_relevance", _fake_score)

    await ai_review_tasks.run_ai_review(case.id, db_session)

    await db_session.refresh(documents[0], attribute_names=["ai_relevance"])
    assert documents[0].ai_relevance.status == AiRelevanceStatus.completed
    assert documents[0].ai_relevance.score == 60


async def test_run_ai_review_default_mode_rescoring_after_criteria_change(db_session, monkeypatch):
    db_session.add(SystemSettings(ai_review_concurrency=1))
    await db_session.commit()

    case = await _make_case(db_session, ai_review_criteria="Original criteria")
    documents = await _seed_documents(db_session, case.id, 1)

    db_session.add(
        DocumentAiRelevance(
            document_id=documents[0].id,
            status=AiRelevanceStatus.completed,
            score=10,
            criteria_snapshot="Original criteria",
        )
    )
    await db_session.commit()

    case.ai_review_criteria = "Updated criteria"
    await db_session.commit()

    async def _fake_score(**kwargs):
        return RelevanceResult(score=90, rationale="Matches the new criteria.")

    monkeypatch.setattr(ai_review_tasks, "score_document_relevance", _fake_score)

    await ai_review_tasks.run_ai_review(case.id, db_session)

    await db_session.refresh(documents[0], attribute_names=["ai_relevance"])
    assert documents[0].ai_relevance.score == 90
    assert documents[0].ai_relevance.criteria_snapshot == "Updated criteria"


async def test_run_ai_review_rescore_all_ignores_up_to_date_scores(db_session, monkeypatch):
    db_session.add(SystemSettings(ai_review_concurrency=1))
    await db_session.commit()

    case = await _make_case(db_session)
    documents = await _seed_documents(db_session, case.id, 1)

    db_session.add(
        DocumentAiRelevance(
            document_id=documents[0].id,
            status=AiRelevanceStatus.completed,
            score=99,
            criteria_snapshot=case.ai_review_criteria,
        )
    )
    await db_session.commit()

    scored_subjects = []

    async def _fake_score(*, subject, **kwargs):
        scored_subjects.append(subject)
        return RelevanceResult(score=33, rationale="Rescored.")

    monkeypatch.setattr(ai_review_tasks, "score_document_relevance", _fake_score)

    await ai_review_tasks.run_ai_review(case.id, db_session, rescore_all=True)

    assert documents[0].subject in scored_subjects
    await db_session.refresh(documents[0], attribute_names=["ai_relevance"])
    assert documents[0].ai_relevance.score == 33
