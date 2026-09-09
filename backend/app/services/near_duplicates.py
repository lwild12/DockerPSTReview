from __future__ import annotations

import hashlib
import random
import re
from dataclasses import dataclass

_WHITESPACE_RE = re.compile(r"\s+")
_ATTRIBUTION_LINE_RE = re.compile(r"^on .+ wrote:$", re.IGNORECASE)

# Large Mersenne prime, the conventional modulus for MinHash's universal hash
# family -- comfortably bigger than any 8-byte shingle digest it hashes.
_MERSENNE_PRIME = (1 << 61) - 1
_HASH_SEED = 0x6E656172647570  # fixed seed so signatures are stable across runs


@dataclass
class NearDupCandidate:
    id: str
    text: str


@dataclass
class NearDupAssignment:
    id: str
    cluster_key: str | None  # None when no near-duplicate was found for this document


def _normalize(text: str) -> str:
    kept_lines = [
        line
        for line in text.splitlines()
        if not line.strip().startswith(">") and not _ATTRIBUTION_LINE_RE.match(line.strip())
    ]
    return _WHITESPACE_RE.sub(" ", " ".join(kept_lines)).strip().lower()


def _shingles(text: str, shingle_size: int) -> set[str]:
    words = text.split(" ")
    words = [w for w in words if w]
    if not words:
        return set()
    if len(words) < shingle_size:
        return {" ".join(words)}
    return {" ".join(words[i : i + shingle_size]) for i in range(len(words) - shingle_size + 1)}


def _hash_coefficients(num_hashes: int) -> list[tuple[int, int]]:
    rng = random.Random(_HASH_SEED)
    return [
        (rng.randrange(1, _MERSENNE_PRIME), rng.randrange(0, _MERSENNE_PRIME))
        for _ in range(num_hashes)
    ]


def _shingle_base_hash(shingle: str) -> int:
    digest = hashlib.blake2b(shingle.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big")


def _minhash_signature(shingles: set[str], coefficients: list[tuple[int, int]]) -> tuple[int, ...]:
    base_hashes = [_shingle_base_hash(s) for s in shingles]
    return tuple(min((a * h + b) % _MERSENNE_PRIME for h in base_hashes) for a, b in coefficients)


def compute_near_duplicate_clusters(
    candidates: list[NearDupCandidate],
    shingle_size: int = 4,
    num_hashes: int = 64,
    num_bands: int = 16,
    jaccard_threshold: float = 0.75,
) -> list[NearDupAssignment]:
    """MinHash + LSH banding over word-shingled text. Candidates with no usable
    text (empty after normalization) are always singletons. Clustering is a
    union-find over verified pairs (same LSH bucket AND estimated Jaccard
    similarity >= jaccard_threshold), matching the pattern used for thread
    assignment in threading_service.assign_threads."""
    if num_hashes % num_bands != 0:
        raise ValueError("num_hashes must be evenly divisible by num_bands")
    rows_per_band = num_hashes // num_bands
    coefficients = _hash_coefficients(num_hashes)

    signatures: dict[str, tuple[int, ...]] = {}
    for c in candidates:
        shingles = _shingles(_normalize(c.text), shingle_size)
        if shingles:
            signatures[c.id] = _minhash_signature(shingles, coefficients)

    buckets: dict[tuple[int, tuple[int, ...]], list[str]] = {}
    for doc_id, signature in signatures.items():
        for band in range(num_bands):
            start = band * rows_per_band
            key = (band, signature[start : start + rows_per_band])
            buckets.setdefault(key, []).append(doc_id)

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

    clustered: set[str] = set()
    for members in buckets.values():
        if len(members) < 2:
            continue
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                a, b = members[i], members[j]
                sig_a, sig_b = signatures[a], signatures[b]
                matches = sum(1 for x, y in zip(sig_a, sig_b, strict=True) if x == y)
                if matches / num_hashes >= jaccard_threshold:
                    union(a, b)
                    clustered.add(a)
                    clustered.add(b)

    groups: dict[str, list[str]] = {}
    for doc_id in clustered:
        groups.setdefault(find(doc_id), []).append(doc_id)

    cluster_key_by_id: dict[str, str] = {}
    for root, members in groups.items():
        if len(members) < 2:
            continue
        for member in members:
            cluster_key_by_id[member] = root

    return [NearDupAssignment(id=c.id, cluster_key=cluster_key_by_id.get(c.id)) for c in candidates]
