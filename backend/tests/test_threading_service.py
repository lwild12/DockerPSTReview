from app.services.threading_service import ThreadCandidate, assign_threads


def test_groups_reply_chain_via_in_reply_to():
    candidates = [
        ThreadCandidate(
            id="1",
            message_id="<root@x>",
            in_reply_to="",
            references=[],
            subject="S",
            participants_key="p",
        ),
        ThreadCandidate(
            id="2",
            message_id="<reply1@x>",
            in_reply_to="<root@x>",
            references=["<root@x>"],
            subject="Re: S",
            participants_key="p",
        ),
        ThreadCandidate(
            id="3",
            message_id="<reply2@x>",
            in_reply_to="<reply1@x>",
            references=["<root@x>", "<reply1@x>"],
            subject="Re: S",
            participants_key="p",
        ),
    ]
    assignments = {a.id: a.thread_key for a in assign_threads(candidates)}
    assert assignments["1"] == assignments["2"] == assignments["3"]


def test_unrelated_messages_stay_in_separate_threads():
    candidates = [
        ThreadCandidate(
            id="1",
            message_id="<a@x>",
            in_reply_to="",
            references=[],
            subject="Alpha",
            participants_key="p1",
        ),
        ThreadCandidate(
            id="2",
            message_id="<b@x>",
            in_reply_to="",
            references=[],
            subject="Beta",
            participants_key="p2",
        ),
    ]
    assignments = {a.id: a.thread_key for a in assign_threads(candidates)}
    assert assignments["1"] != assignments["2"]


def test_fallback_groups_by_normalized_subject_and_participants_when_no_message_id():
    candidates = [
        ThreadCandidate(
            id="1",
            message_id="",
            in_reply_to="",
            references=[],
            subject="Budget review",
            participants_key="p",
        ),
        ThreadCandidate(
            id="2",
            message_id="",
            in_reply_to="",
            references=[],
            subject="Re: Budget review",
            participants_key="p",
        ),
    ]
    assignments = {a.id: a.thread_key for a in assign_threads(candidates)}
    assert assignments["1"] == assignments["2"]


def test_fallback_does_not_merge_different_participants():
    candidates = [
        ThreadCandidate(
            id="1",
            message_id="",
            in_reply_to="",
            references=[],
            subject="Budget",
            participants_key="team-a",
        ),
        ThreadCandidate(
            id="2",
            message_id="",
            in_reply_to="",
            references=[],
            subject="Budget",
            participants_key="team-b",
        ),
    ]
    assignments = {a.id: a.thread_key for a in assign_threads(candidates)}
    assert assignments["1"] != assignments["2"]


def test_reply_referencing_unseen_root_still_links_when_root_appears():
    # References may point to a message-id we haven't processed as its own row yet
    # (e.g. root wasn't recovered) — should still union correctly if root IS present.
    candidates = [
        ThreadCandidate(
            id="1",
            message_id="<root@x>",
            in_reply_to="",
            references=[],
            subject="S",
            participants_key="p",
        ),
        ThreadCandidate(
            id="2",
            message_id="<child@x>",
            in_reply_to="<root@x>",
            references=["<root@x>"],
            subject="Re: S",
            participants_key="p",
        ),
    ]
    assignments = {a.id: a.thread_key for a in assign_threads(candidates)}
    assert assignments["1"] == assignments["2"]
