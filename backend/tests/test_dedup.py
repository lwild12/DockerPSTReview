from datetime import datetime, timedelta

from app.services.dedup import (
    DedupCandidate,
    assign_dedup_status,
    compute_attachment_hash,
    compute_email_hash,
    normalize_subject,
)


def test_normalize_subject_strips_repeated_prefixes():
    assert normalize_subject("Re: Fwd: RE: Quarterly report") == "quarterly report"
    assert normalize_subject("Quarterly report") == "quarterly report"
    assert normalize_subject("  Fw:   Budget  ") == "budget"


def test_compute_email_hash_is_order_independent_for_recipients():
    h1 = compute_email_hash("a@x.com", ["b@x.com", "c@x.com"], [], [], "Subject", "body text", [])
    h2 = compute_email_hash(
        "a@x.com", ["c@x.com", "b@x.com"], [], [], "Re: Subject", "body   text", []
    )
    assert h1 == h2


def test_compute_email_hash_differs_on_body_change():
    h1 = compute_email_hash("a@x.com", ["b@x.com"], [], [], "S", "body one", [])
    h2 = compute_email_hash("a@x.com", ["b@x.com"], [], [], "S", "body two", [])
    assert h1 != h2


def test_compute_attachment_hash_is_deterministic():
    assert compute_attachment_hash(b"hello") == compute_attachment_hash(b"hello")
    assert compute_attachment_hash(b"hello") != compute_attachment_hash(b"world")


def test_assign_dedup_status_groups_by_hash_earliest_wins():
    base = datetime(2024, 1, 1)
    candidates = [
        DedupCandidate(id="1", content_hash="H1", created_at=base + timedelta(hours=2)),
        DedupCandidate(id="2", content_hash="H1", created_at=base),
        DedupCandidate(id="3", content_hash="H1", created_at=base + timedelta(hours=1)),
        DedupCandidate(id="4", content_hash="H2", created_at=base),
    ]
    results = {r.id: r for r in assign_dedup_status(candidates)}

    assert results["2"].is_duplicate is False
    assert results["2"].duplicate_of_id is None
    assert results["1"].is_duplicate is True
    assert results["1"].duplicate_of_id == "2"
    assert results["3"].is_duplicate is True
    assert results["3"].duplicate_of_id == "2"
    assert results["4"].is_duplicate is False


def test_assign_dedup_status_treats_empty_hash_as_unique():
    candidates = [
        DedupCandidate(id="1", content_hash="", created_at=datetime(2024, 1, 1)),
        DedupCandidate(id="2", content_hash="", created_at=datetime(2024, 1, 2)),
    ]
    results = {r.id: r for r in assign_dedup_status(candidates)}
    assert results["1"].is_duplicate is False
    assert results["2"].is_duplicate is False
