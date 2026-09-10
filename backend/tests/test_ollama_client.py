import json

import httpx
import pytest

from app.services.ollama_client import OllamaError, score_document_relevance


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


async def test_scoring_logs_a_preview_of_what_was_sent_and_received(caplog):
    # Diagnostic aid: an admin unsure whether real document content is
    # reaching the model (the original "subject and sender only" bug) can
    # check `docker compose logs worker` rather than needing a debugger.
    def handler(request):
        return httpx.Response(
            200, json={"response": json.dumps({"score": 42, "rationale": "Somewhat relevant."})}
        )

    with caplog.at_level("INFO", logger="app.services.ollama_client"):
        async with _client_for(handler) as client:
            await _score(client, body="Here is the Q3 budget breakdown.")

    log_text = "\n".join(caplog.messages)
    assert "Here is the Q3 budget breakdown." in log_text
    assert "score=42" in log_text
