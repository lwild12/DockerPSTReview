from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ThreadMemberCandidate:
    id: str
    message_id: str
    in_reply_to: str
    references: list[str]


@dataclass
class InclusivenessResult:
    id: str
    is_inclusive: bool


def compute_inclusiveness(candidates: list[ThreadMemberCandidate]) -> list[InclusivenessResult]:
    """A message is "inclusive" if it captures the full quoted history of the
    conversation up to that point -- in practice, the leaf messages of a reply
    tree (nothing in the thread replies to or quotes them), since mail clients
    normally embed the prior message when replying/forwarding. Messages that
    are themselves referenced by another member of the same thread are marked
    non-inclusive: their content is redundant with that later message.

    Callers should pass only the members of a single thread. Threads of one
    (or messages with no Message-ID to resolve) are trivially inclusive."""
    referenced_ids = {
        ref
        for c in candidates
        for ref in ([c.in_reply_to] if c.in_reply_to else []) + c.references
        if ref
    }
    return [
        InclusivenessResult(
            id=c.id, is_inclusive=not c.message_id or c.message_id not in referenced_ids
        )
        for c in candidates
    ]
