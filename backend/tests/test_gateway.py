"""Gateway adapter tests with a fake HTTP transport."""
from __future__ import annotations

import asyncio
import json

import pytest

from app.gateway import base as gateway_base
from app.gateway.base import (
    GeminiProvider,
    OpenCodeProvider,
    OpenRouterProvider,
    ProviderConfig,
    ProviderError,
    extract_json,
)
from app.schemas import GatewayRequest


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text if text is not None else json.dumps(self._payload)

    def json(self):
        return self._payload


class FakeAsyncClient:
    calls: list[dict] = []
    handler = None

    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs
        self.auth = kwargs.get("auth")

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, json=None, headers=None, **kwargs):
        FakeAsyncClient.calls.append({"method": "POST", "url": url, "json": json, "headers": headers})
        return FakeAsyncClient.handler("POST", url, json, headers)

    async def get(self, url, headers=None, **kwargs):
        FakeAsyncClient.calls.append({"method": "GET", "url": url, "headers": headers})
        return FakeAsyncClient.handler("GET", url, None, headers)

    async def delete(self, url, **kwargs):
        FakeAsyncClient.calls.append({"method": "DELETE", "url": url})
        return FakeAsyncClient.handler("DELETE", url, None, None)


@pytest.fixture(autouse=True)
def fake_transport(monkeypatch):
    FakeAsyncClient.calls = []
    monkeypatch.setattr(gateway_base.httpx, "AsyncClient", FakeAsyncClient)
    yield


def request() -> GatewayRequest:
    return GatewayRequest(messages=[{"role": "user", "content": "hello"}], max_tokens=100)


def test_extract_json_variants():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Sure, here you go: {"a": [1, 2]} thanks') == {"a": [1, 2]}
    with pytest.raises(ProviderError):
        extract_json("no json here")


def test_openrouter_success_and_headers():
    def handler(method, url, payload, headers):
        assert url.endswith("/chat/completions")
        assert payload["model"] == "openrouter/free"
        assert headers["Authorization"] == "Bearer secret"
        return FakeResponse(
            payload={
                "choices": [{"message": {"content": "ready"}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 2},
            }
        )

    FakeAsyncClient.handler = handler
    provider = OpenRouterProvider(
        ProviderConfig(
            provider="openrouter",
            api_key="secret",
            base_url="https://openrouter.ai/api/v1",
            model="openrouter/free",
        )
    )
    response = asyncio.run(provider.generate(request()))
    assert response.content == "ready"
    assert response.prompt_tokens == 5
    assert response.provider == "openrouter"


def test_openrouter_rate_limit_is_retryable():
    FakeAsyncClient.handler = lambda *args: FakeResponse(429, text="rate limited")
    provider = OpenRouterProvider(
        ProviderConfig(
            provider="openrouter",
            api_key="secret",
            base_url="https://openrouter.ai/api/v1",
            model="openrouter/free",
        )
    )
    with pytest.raises(ProviderError) as exc:
        asyncio.run(provider.generate(request()))
    assert exc.value.retryable is True
    assert exc.value.status == 429


def test_gemini_payload_and_usage():
    def handler(method, url, payload, headers):
        assert "generateContent" in url
        assert payload["contents"][0]["parts"][0]["text"] == "hello"
        return FakeResponse(
            payload={
                "candidates": [{"content": {"parts": [{"text": "gemini says hi"}]}}],
                "usageMetadata": {"promptTokenCount": 4, "candidatesTokenCount": 3},
            }
        )

    FakeAsyncClient.handler = handler
    provider = GeminiProvider(
        ProviderConfig(
            provider="gemini",
            api_key="key",
            base_url="https://generativelanguage.googleapis.com/v1beta",
            model="gemini-2.0-flash",
        )
    )
    response = asyncio.run(provider.generate(request()))
    assert response.content == "gemini says hi"
    assert response.completion_tokens == 3


def test_opencode_session_lifecycle():
    def handler(method, url, payload, headers):
        if method == "POST" and url.endswith("/session"):
            return FakeResponse(payload={"id": "sess-1"})
        if method == "POST" and url.endswith("/session/sess-1/message"):
            assert payload["parts"][0]["text"].startswith("USER:")
            return FakeResponse(
                payload={"info": {"role": "assistant"}, "parts": [{"type": "text", "text": "session reply"}]}
            )
        if method == "DELETE":
            return FakeResponse(payload={})
        raise AssertionError(f"Unexpected call {method} {url}")

    FakeAsyncClient.handler = handler
    provider = OpenCodeProvider(
        ProviderConfig(
            provider="opencode",
            api_key="password",
            base_url="http://127.0.0.1:8080",
            model="opencode",
        ),
        username="opencode",
    )
    response = asyncio.run(provider.generate(request()))
    assert response.content == "session reply"
    methods = [c["method"] for c in FakeAsyncClient.calls]
    assert methods == ["POST", "POST", "DELETE"]
    assert all(c["url"].startswith("http://127.0.0.1:8080/session") for c in FakeAsyncClient.calls)


def test_opencode_extract_text_from_history():
    payload = [
        {"info": {"role": "user"}, "parts": [{"type": "text", "text": "question"}]},
        {"info": {"role": "assistant"}, "parts": [{"type": "text", "text": "answer"}]},
    ]
    assert OpenCodeProvider._extract_text(payload, prefer_last=True) == "answer"


def test_not_configured_provider():
    provider = GeminiProvider(ProviderConfig(provider="gemini"))
    with pytest.raises(ProviderError):
        asyncio.run(provider.generate(request()))
