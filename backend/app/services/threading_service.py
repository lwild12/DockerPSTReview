from __future__ import annotations

from dataclasses import dataclass

from app.services.dedup import normalize_subject


@dataclass
class ThreadCandidate:
    id: str
    message_id: str
    in_reply_to: str
    references: list[str]
    subject: str
    participants_key: str  # caller-computed, e.g. sorted+joined sender+recipients


@dataclass
class ThreadAssignment:
    id: str
    thread_key: str  # stable group key; caller maps this to a Thread row


def assign_threads(candidates: list[ThreadCandidate]) -> list[ThreadAssignment]:
    """Union-find over Message-ID/In-Reply-To/References chains. Items with no
    message-id links at all fall back to grouping by (normalized subject, participants).

    Simplification: the subject/participants fallback has no time-window bound, so
    two unrelated conversations that happen to share an exact subject and participant
    set will be merged — acceptable for now, worth revisiting once tested against
    real-world PST samples with high message volume.
    """
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent.setdefault(parent[x], parent[x])
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    def node_key(c: ThreadCandidate) -> str:
        return c.message_id or f"__doc__:{c.id}"

    for c in candidates:
        me = node_key(c)
        find(me)
        for other in ([c.in_reply_to] if c.in_reply_to else []) + c.references:
            if other:
                union(me, other)

    groups: dict[str, list[ThreadCandidate]] = {}
    for c in candidates:
        groups.setdefault(find(node_key(c)), []).append(c)

    fallback_key_to_root: dict[tuple[str, str], str] = {}
    for root, members in groups.items():
        if len(members) > 1:
            continue
        only = members[0]
        if only.message_id:
            continue
        fb_key = (normalize_subject(only.subject), only.participants_key)
        if fb_key in fallback_key_to_root:
            union(root, fallback_key_to_root[fb_key])
        else:
            fallback_key_to_root[fb_key] = root

    return [ThreadAssignment(id=c.id, thread_key=find(node_key(c))) for c in candidates]
