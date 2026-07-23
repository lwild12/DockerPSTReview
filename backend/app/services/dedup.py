from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

_REPLY_PREFIX_RE = re.compile(r"^(re|fwd?|fw)\s*:\s*", re.IGNORECASE)


def normalize_subject(subject: str) -> str:
    """Strip repeated Re:/Fwd:/Fw: prefixes and normalize case/whitespace."""
    normalized = subject.strip()
    while True:
        stripped = _REPLY_PREFIX_RE.sub("", normalized).strip()
        if stripped == normalized:
            break
        normalized = stripped
    return normalized.lower()


def compute_email_hash(
    sender: str,
    recipients_to: list[str],
    recipients_cc: list[str],
    recipients_bcc: list[str],
    subject: str,
    body_text: str,
    attachment_hashes: list[str],
) -> str:
    """Canonical content hash for email dedup: normalized headers + body + attachment hashes."""
    parts = [
        sender.strip().lower(),
        ",".join(sorted(a.strip().lower() for a in recipients_to)),
        ",".join(sorted(a.strip().lower() for a in recipients_cc)),
        ",".join(sorted(a.strip().lower() for a in recipients_bcc)),
        normalize_subject(subject),
        " ".join(body_text.split()),
        ",".join(sorted(attachment_hashes)),
    ]
    canonical = "\x1f".join(parts)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_attachment_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


@dataclass
class DedupCandidate:
    id: str
    content_hash: str
    created_at: Any  # any orderable value, e.g. datetime


@dataclass
class DedupResult:
    id: str
    is_duplicate: bool
    duplicate_of_id: str | None


def assign_dedup_status(candidates: list[DedupCandidate]) -> list[DedupResult]:
    """Group candidates by content_hash; the earliest `created_at` in each group is
    the primary, the rest are marked as duplicates of it. Candidates with an empty
    hash (nothing to compare) are always primary."""
    by_hash: dict[str, list[DedupCandidate]] = {}
    for c in candidates:
        if c.content_hash:
            by_hash.setdefault(c.content_hash, []).append(c)

    results: dict[str, DedupResult] = {}
    for group in by_hash.values():
        ordered = sorted(group, key=lambda c: c.created_at)
        primary = ordered[0]
        results[primary.id] = DedupResult(id=primary.id, is_duplicate=False, duplicate_of_id=None)
        for dup in ordered[1:]:
            results[dup.id] = DedupResult(id=dup.id, is_duplicate=True, duplicate_of_id=primary.id)

    for c in candidates:
        if c.id not in results:
            results[c.id] = DedupResult(id=c.id, is_duplicate=False, duplicate_of_id=None)

    return list(results.values())
