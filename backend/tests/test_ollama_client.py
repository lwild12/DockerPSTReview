import json
import logging

import httpx
import pytest

from app.services.ollama_client import OllamaError, score_document_relevance
from app.services.ollama_client import logger as ollama_logger


def _client_for(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def _score(client, **overrides):
    kwargs = dict(
        base_url="http://ollama.local:11434",
        model="llama3.1",
        api_key="",
        criteria="Documents discussing the Q3 budget",
        subject="Q3 numbers",
        sender="alice@example.com",
        body="Here is the Q3 budget breakdown.",
        client=client,
    )
    kwargs.update(overrides)
    return await score_document_relevance(**kwargs)


async def test_well_formed_response_parses_correctly():
    def handler(request):
        return httpx.Response(
            200,
            json={"response": json.dumps({"score": 82, "rationale": "Directly about Q3 budget."})},
        )

    async with _client_for(handler) as client:
        result = await _score(client)
    assert result.score == 82
    assert result.rationale == "Directly about Q3 budget."


async def test_json_wrapped_in_prose_is_still_extracted():
    # Some models ignore the format:"json" constraint and add commentary.
    def handler(request):
        return httpx.Response(
            200,
            json={"response": 'Sure: {"score": 40, "rationale": "Tangential."} Hope that helps!'},
        )

    async with _client_for(handler) as client:
        result = await _score(client)
    assert result.score == 40
    assert result.rationale == "Tangential."


async def test_score_out_of_range_is_clipped_not_rejected():
    def handler(request):
        return httpx.Response(
            200, json={"response": json.dumps({"score": 150, "rationale": "Very relevant."})}
        )

    async with _client_for(handler) as client:
        result = await _score(client)
    assert result.score == 100


async def test_negative_score_is_clipped_to_zero():
    def handler(request):
        return httpx.Response(
            200, json={"response": json.dumps({"score": -20, "rationale": "Not relevant."})}
        )

    async with _client_for(handler) as client:
        result = await _score(client)
    assert result.score == 0


async def test_non_json_garbage_raises_ollama_error():
    def handler(request):
        return httpx.Response(200, json={"response": "not json at all, sorry"})

    async with _client_for(handler) as client:
        with pytest.raises(OllamaError):
            await _score(client)


async def test_missing_score_field_raises_ollama_error():
    def handler(request):
        return httpx.Response(200, json={"response": json.dumps({"rationale": "no score here"})})

    async with _client_for(handler) as client:
        with pytest.raises(OllamaError):
            await _score(client)


async def test_boolean_score_is_rejected():
    # bool is a subclass of int in Python -- must not silently pass as a score.
    def handler(request):
        return httpx.Response(200, json={"response": json.dumps({"score": True, "rationale": "x"})})

    async with _client_for(handler) as client:
        with pytest.raises(OllamaError):
            await _score(client)


async def test_non_200_response_raises_ollama_error():
    def handler(request):
        return httpx.Response(500, text="internal error")

    async with _client_for(handler) as client:
        with pytest.raises(OllamaError):
            await _score(client)


async def test_connection_error_raises_ollama_error():
    def handler(request):
        raise httpx.ConnectError("connection refused")

    async with _client_for(handler) as client:
        with pytest.raises(OllamaError):
            await _score(client)


async def test_auth_header_only_sent_when_api_key_provided():
    seen_headers = {}

    def handler(request):
        seen_headers.update(request.headers)
        return httpx.Response(200, json={"response": json.dumps({"score": 50, "rationale": "x"})})

    async with _client_for(handler) as client:
        await _score(client, api_key="")
    assert "authorization" not in seen_headers

    async with _client_for(handler) as client:
        await _score(client, api_key="secret-token")
    assert seen_headers.get("authorization") == "Bearer secret-token"


async def test_unconfigured_ollama_raises_without_making_a_request():
    called = False

    def handler(request):
        nonlocal called
        called = True
        return httpx.Response(200, json={"response": "{}"})

    async with _client_for(handler) as client:
        with pytest.raises(OllamaError):
            await _score(client, base_url="")
    assert not called


async def test_long_document_body_is_truncated_in_the_prompt():
    seen_request = {}

    def handler(request):
        seen_request["body"] = json.loads(request.content)
        return httpx.Response(200, json={"response": json.dumps({"score": 10, "rationale": "x"})})

    async with _client_for(handler) as client:
        await _score(client, body="x" * 20000)

    assert len(seen_request["body"]["prompt"]) < 15000


async def test_scoring_does_not_log_by_default(caplog):
    # Document content is potentially privileged/sensitive -- nothing about
    # a scoring request/response should be logged anywhere unless an admin
    # has explicitly opted in via the "Log Ollama requests" setting.
    def handler(request):
        return httpx.Response(
            200, json={"response": json.dumps({"score": 42, "rationale": "Somewhat relevant."})}
        )

    with caplog.at_level("DEBUG", logger="app.services.ollama_client"):
        async with _client_for(handler) as client:
            await _score(client, body="Here is the Q3 budget breakdown.")

    assert caplog.messages == []


async def test_scoring_logs_a_preview_of_what_was_sent_and_received_when_enabled(caplog):
    # Diagnostic aid: an admin unsure whether real document content is
    # reaching the model (the original "subject and sender only" bug) can
    # check `docker compose logs worker`/ollama.log rather than needing a
    # debugger -- once they've opted in via log_requests.
    def handler(request):
        return httpx.Response(
            200, json={"response": json.dumps({"score": 42, "rationale": "Somewhat relevant."})}
        )

    with caplog.at_level("INFO", logger="app.services.ollama_client"):
        async with _client_for(handler) as client:
            await _score(client, body="Here is the Q3 budget breakdown.", log_requests=True)

    log_text = "\n".join(caplog.messages)
    assert "Here is the Q3 budget breakdown." in log_text
    assert "score=42" in log_text


async def test_scoring_log_preview_marks_truncation_instead_of_stopping_silently(caplog):
    # Reported as "body is being truncated": the preview snippet in the log
    # line used to cut off at exactly 200 chars with no indication it was
    # only a preview, mid-word and all -- read as if the model's actual
    # input had been cut short, when the full (correctly reported) length
    # was always what's actually sent. The preview should say so.
    def handler(request):
        return httpx.Response(200, json={"response": json.dumps({"score": 10, "rationale": "x"})})

    long_body = "word " * 100  # well over the 200-char preview limit
    with caplog.at_level("INFO", logger="app.services.ollama_client"):
        async with _client_for(handler) as client:
            await _score(client, body=long_body, log_requests=True)

    log_text = "\n".join(caplog.messages)
    assert "chars total" in log_text
    assert f"body is {len(long_body)} chars" in log_text


def test_logger_fires_info_even_when_root_logger_is_warning():
    # uvicorn's default logging setup (used by the `backend` container, the
    # per-document re-run button's entry point) leaves an unconfigured
    # logger like this one at the root's default WARNING, silently
    # dropping every INFO call above -- confirmed via a real
    # uvicorn.config.Config().configure_logging() call. The exact same
    # code worked when triggered via `worker` only because Celery's
    # --loglevel=INFO happens to set the root logger to INFO, masking the
    # bug there. caplog.at_level (used above) forces the level and would
    # mask this too, so this test sets the root level directly instead.
    root = logging.getLogger()
    original_root_level = root.level
    try:
        root.setLevel(logging.WARNING)
        assert ollama_logger.isEnabledFor(logging.INFO)
    finally:
        root.setLevel(original_root_level)
