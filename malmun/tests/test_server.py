"""Tests for the local relay. Run from the malmun folder: python -m pytest tests"""

import sys
from pathlib import Path
from types import SimpleNamespace

import anthropic
import httpx2
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server  # noqa: E402

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["reply"],
    "properties": {"reply": {"type": "string"}},
}


class FakeMessages:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


def message(text='{"reply": "Hi there!"}', stop_reason="end_turn"):
    return SimpleNamespace(
        stop_reason=stop_reason,
        content=[
            SimpleNamespace(type="thinking", thinking=""),
            SimpleNamespace(type="text", text=text),
        ],
    )


def api_error(cls, status):
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls("error", response=httpx2.Response(status, request=request), body=None)


@pytest.fixture
def fake(monkeypatch):
    messages = FakeMessages(response=message())
    monkeypatch.setattr(server, "client", SimpleNamespace(beta=SimpleNamespace(messages=messages), api_key="test-key"))
    return messages


def fake_client():
    return server.client


@pytest.fixture
def http():
    return TestClient(server.app)


def ask(http, **overrides):
    body = {"system": "You are a tutor.", "prompt": "Say hi.", "schema": SCHEMA, "tier": "quick"}
    body.update(overrides)
    return http.post("/api/claude", json=body)


def test_index_wraps_the_artifact_page(http):
    r = http.get("/")
    assert r.status_code == 200
    assert r.text.startswith("<!doctype html>")
    assert "<title>말문 English</title>" in r.text
    assert r.text.endswith("</body></html>")


def test_health_reports_credentials(http, fake, monkeypatch):
    assert http.get("/api/health").json() == {"ok": True, "ai": True, "model": server.MODEL}
    monkeypatch.setattr(fake_client(), "api_key", None)
    assert http.get("/api/health").json()["ai"] is False


def test_missing_credentials_is_reported_without_calling_the_api(http, fake, monkeypatch):
    monkeypatch.setattr(fake_client(), "api_key", None)
    r = ask(http)
    assert r.status_code == 401
    assert "ANTHROPIC_API_KEY" in r.json()["detail"]
    assert fake.calls == []


def test_relays_structured_request_and_returns_parsed_json(http, fake):
    r = ask(http)
    assert r.status_code == 200
    assert r.json() == {"reply": "Hi there!"}
    call = fake.calls[0]
    assert call["model"] == server.MODEL
    assert call["system"] == "You are a tutor."
    assert call["messages"] == [{"role": "user", "content": "Say hi."}]
    assert call["output_config"] == {"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}}
    assert call["fallbacks"] == "default"
    assert call["betas"] == ["server-side-fallback-2026-07-01"]


def test_default_tier_uses_more_effort(http, fake):
    ask(http, tier="default")
    assert fake.calls[0]["output_config"]["effort"] == "medium"


def test_refusal_is_reported(http, fake):
    fake.response = message(text="", stop_reason="refusal")
    assert ask(http).status_code == 422


def test_truncated_answer_is_reported(http, fake):
    fake.response = message(text='{"reply": "Hi', stop_reason="max_tokens")
    assert ask(http).status_code == 502


@pytest.mark.parametrize(
    ("error_cls", "status", "expected"),
    [
        (anthropic.AuthenticationError, 401, 401),
        (anthropic.RateLimitError, 429, 429),
        (anthropic.InternalServerError, 500, 502),
    ],
)
def test_api_errors_map_to_http_errors(http, fake, error_cls, status, expected):
    fake.error = api_error(error_cls, status)
    r = ask(http)
    assert r.status_code == expected
    assert isinstance(r.json()["detail"], str)


def test_rejects_bad_input(http, fake):
    assert ask(http, prompt="").status_code == 422
    assert ask(http, tier="max").status_code == 422
    assert fake.calls == []
