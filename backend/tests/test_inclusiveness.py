from app.services.inclusiveness import ThreadMemberCandidate, compute_inclusiveness


def test_leaf_message_is_inclusive_ancestors_are_not():
    candidates = [
        ThreadMemberCandidate(id="1", message_id="<root@x>", in_reply_to="", references=[]),
        ThreadMemberCandidate(
            id="2", message_id="<reply1@x>", in_reply_to="<root@x>", references=["<root@x>"]
        ),
        ThreadMemberCandidate(
            id="3",
            message_id="<reply2@x>",
            in_reply_to="<reply1@x>",
            references=["<root@x>", "<reply1@x>"],
        ),
    ]
    results = {r.id: r.is_inclusive for r in compute_inclusiveness(candidates)}
    assert results == {"1": False, "2": False, "3": True}


def test_branching_thread_marks_every_leaf_inclusive():
    root = ThreadMemberCandidate(id="1", message_id="<root@x>", in_reply_to="", references=[])
    branch_a = ThreadMemberCandidate(
        id="2", message_id="<a@x>", in_reply_to="<root@x>", references=["<root@x>"]
    )
    branch_b = ThreadMemberCandidate(
        id="3", message_id="<b@x>", in_reply_to="<root@x>", references=["<root@x>"]
    )
    results = {r.id: r.is_inclusive for r in compute_inclusiveness([root, branch_a, branch_b])}
    assert results == {"1": False, "2": True, "3": True}


def test_single_member_thread_is_trivially_inclusive():
    candidates = [ThreadMemberCandidate(id="1", message_id="<a@x>", in_reply_to="", references=[])]
    results = compute_inclusiveness(candidates)
    assert len(results) == 1
    assert results[0].is_inclusive is True


def test_messages_with_no_message_id_default_to_inclusive():
    candidates = [
        ThreadMemberCandidate(id="1", message_id="<root@x>", in_reply_to="", references=[]),
        ThreadMemberCandidate(
            id="2", message_id="", in_reply_to="<root@x>", references=["<root@x>"]
        ),
    ]
    results = {r.id: r.is_inclusive for r in compute_inclusiveness(candidates)}
    # "1" is referenced by "2" so it's superseded; "2" has no message-id of its own
    # to check against, so there's no way to know if anything supersedes it.
    assert results == {"1": False, "2": True}
