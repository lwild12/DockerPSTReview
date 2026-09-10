from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from logging import FileHandler

import httpx

logger = logging.getLogger(__name__)
# Set explicitly rather than relying on the ambient root level: uvicorn's
# default logging setup (used by the `backend` container) leaves an
# unconfigured logger like this one at the root's default WARNING, which
# silently drops every INFO call below without raising anything -- the
# previous version of this file had none of its scoring logs show up
# anywhere when triggered via the backend (the per-document re-run
# button), console or file, even though the exact same code worked from
# the `worker` container (Celery's --loglevel=INFO happens to set the
# root logger to INFO, masking the bug there). Confirmed via a real
# uvicorn Config().configure_logging() call.
logger.setLevel(logging.INFO)

# `docker compose logs` has proven awkward for admins to actually find these
# lines in (they're interleaved with everything else the backend/worker
# containers log, and there are two containers to check depending on which
# entry point triggered the scoring). Mirror the same INFO-level preview to
# a plain file at a fixed path -- docker-compose.yml bind-mounts this to
# ollama.log next to the compose file, so `tail -f ollama.log` on the host
# works regardless of which container is doing the scoring. Best-effort:
# outside the container (local dev, tests) this path doesn't exist and
# logging still works fine via the normal handler.
_LOG_FILE_PATH = "/var/log/ollama.log"
try:
    _file_handler = FileHandler(_LOG_FILE_PATH)
except OSError:
    pass
else:
    _file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    _file_handler.setLevel(logging.INFO)
    logger.addHandler(_file_handler)

# Named constant rather than inline so it's easy to iterate on post-launch
# without touching the request/parsing logic around it. There's no eval
# harness in this repo to validate prompt quality against real documents --
# this is a reasonable first pass (JSON-constrained output, explicit
# assistive/non-final framing, 0-100 scale, short rationale), not a tuned
# one. One issue already found this way: several models default to a 0-10
# (or 1-5) convention for "relevance scoring" regardless of what range the
# prompt asks for, silently producing only the two extremes (0 and 10) of
# their own internal scale -- both values pass our [0,100] validation
# untouched, since they're valid integers in range, so nothing downstream
# catches it. The calibration bands and explicit "not 0-10" callout below
# are a direct response to that, not speculative -- keep iterating on this
# the same way if a particular model still clusters its scores.
SYSTEM_PROMPT = (
    "You are assisting a human legal document reviewer during pre-review "
    "triage. Your output is advisory only and will always be checked by a "
    "human -- you are not making a final relevance determination. Given the "
    "case's relevance criteria and a document's content, respond with ONLY "
    'a JSON object of this exact shape: {"score": <integer 0-100>, '
    '"rationale": <string, 1-2 sentences>} -- no other text.\n\n'
    "`score` is how likely the document is relevant to the stated criteria, "
    "on a scale of 0 to 100 -- a percentage-style estimate, NOT a 0-10 or "
    "1-5 scale. Use the full range and pick a specific number rather than "
    "always rounding to a multiple of 10. Rough calibration:\n"
    "0-10: clearly unrelated to the criteria\n"
    "11-39: unlikely to be relevant -- at most a passing or tangential mention\n"
    "40-69: plausibly relevant -- touches the subject but not squarely\n"
    "70-89: likely relevant -- substantively discusses the criteria\n"
    "90-100: unmistakably and directly about the criteria"
)

# A large document is truncated to a crude character budget rather than
# something token-aware -- no tokenizer is wired up for arbitrary Ollama
# models, and this keeps one oversized document from blowing the prompt.
_MAX_DOCUMENT_CHARS = 8000
_MAX_RATIONALE_CHARS = 1000
_DEFAULT_TIMEOUT_SECONDS = 120.0


class OllamaError(Exception):
    """Anything that keeps a document from getting a usable relevance score
    -- a network/timeout failure, a non-2xx response, or a response that
    doesn't parse into a valid score. Callers mark the document `failed`
    with this message rather than guessing a score, since a plausible-
    looking wrong score on an assistive tool is worse than an honest
    "scoring failed, needs a human anyway"."""


@dataclass
class RelevanceResult:
    score: int
    rationale: str


def _build_user_prompt(criteria: str, subject: str, sender: str, body: str) -> str:
    truncated_body = body[:_MAX_DOCUMENT_CHARS]
    return (
        f"Relevance criteria:\n{criteria}\n\n"
        f"Document:\nSubject: {subject}\nFrom: {sender}\n\n{truncated_body}"
    )


def _extract_json_object(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Ollama's `format: "json"` constrains output, but some models still
    # wrap the object in prose -- try pulling out the first {...} substring
    # before giving up.
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    raise OllamaError(f"Model response was not valid JSON: {text[:500]!r}")


def _parse_relevance_result(raw_response_text: str) -> RelevanceResult:
    data = _extract_json_object(raw_response_text)
    score = data.get("score") if isinstance(data, dict) else None
    if not isinstance(score, int | float) or isinstance(score, bool):
        raise OllamaError(f"Model response missing a numeric score: {raw_response_text[:500]!r}")
    clipped_score = max(0, min(100, int(score)))
    rationale = data.get("rationale") if isinstance(data, dict) else None
    if not isinstance(rationale, str) or not rationale.strip():
        raise OllamaError(f"Model response missing a rationale: {raw_response_text[:500]!r}")
    return RelevanceResult(score=clipped_score, rationale=rationale.strip()[:_MAX_RATIONALE_CHARS])


async def score_document_relevance(
    *,
    base_url: str,
    model: str,
    api_key: str,
    criteria: str,
    subject: str,
    sender: str,
    body: str,
    timeout: float = _DEFAULT_TIMEOUT_SECONDS,
    client: httpx.AsyncClient | None = None,
) -> RelevanceResult:
    """Score one document's relevance against `criteria` via an
    Ollama-compatible `/api/generate` endpoint. `client` is injectable for
    tests (e.g. one built on `httpx.MockTransport`); by default a fresh
    client is opened and closed per call."""
    if not base_url or not model:
        raise OllamaError(
            "Ollama is not configured -- set the endpoint URL and model in Admin settings"
        )

    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    user_prompt = _build_user_prompt(criteria, subject, sender, body)
    payload = {
        "model": model,
        "system": SYSTEM_PROMPT,
        "prompt": user_prompt,
        "format": "json",
        "stream": False,
    }

    # INFO: a bounded preview -- enough to sanity-check that real document
    # content is actually reaching the model (the original bug this is a
    # response to) without routinely dumping full, potentially sensitive
    # document bodies into the worker's default log level. DEBUG carries
    # the whole prompt for when that's not enough.
    logger.info(
        "AI review: scoring subject=%r against model=%s -- body is %d chars, starts: %r",
        subject[:200],
        model,
        len(body),
        body[:200],
    )
    logger.debug("AI review: full prompt sent to Ollama:\n%s", user_prompt)

    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=timeout, write=10.0, pool=10.0)
        )
    try:
        try:
            resp = await client.post(
                f"{base_url.rstrip('/')}/api/generate", json=payload, headers=headers
            )
        except httpx.HTTPError as exc:
            raise OllamaError(f"Could not reach Ollama at {base_url}: {exc}") from exc

        if resp.status_code != 200:
            raise OllamaError(f"Ollama returned HTTP {resp.status_code}: {resp.text[:500]}")

        try:
            response_body = resp.json()
        except ValueError as exc:
            raise OllamaError(f"Ollama response was not valid JSON: {resp.text[:500]!r}") from exc

        response_text = response_body.get("response") if isinstance(response_body, dict) else None
        if not isinstance(response_text, str):
            raise OllamaError(f"Ollama response missing 'response' field: {response_body!r:.500}")

        logger.info("AI review: raw model response: %r", response_text[:500])
        result = _parse_relevance_result(response_text)
        logger.info("AI review: parsed score=%d rationale=%r", result.score, result.rationale)
        return result
    finally:
        if owns_client:
            await client.aclose()
