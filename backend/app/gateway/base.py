"""Provider-independent LLM gateway primitives.

Agents only ever see :class:`BaseProvider` and :class:`GatewayManager`; every
provider-specific detail (OpenAI-compatible HTTP, Gemini REST, OpenCode sessions)
lives in an adapter. Provider errors never leak into agent logic as anything other
than :class:`ProviderError`.
"""
from __future__ import annotations

import abc
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from ..schemas import ChatMessage, GatewayRequest, GatewayResponse, ProviderHealth

TModel = TypeVar("TModel", bound=BaseModel)


class ProviderError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = False, status: int | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.status = status


class ProviderNotConfigured(ProviderError):
    def __init__(self, provider: str):
        super().__init__(f"Provider '{provider}' is not configured", retryable=False)
        self.provider = provider


@dataclass
class ProviderConfig:
    provider: str
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    temperature: float = 0.3
    max_tokens: int = 1500
    is_paid: bool = False
    enabled: bool = True
    agent_overrides: dict[str, dict[str, str]] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def configured(self) -> bool:
        if self.provider == "ollama":
            return bool(self.base_url)
        if self.provider == "heuristic":
            return True
        return bool(self.api_key and self.base_url)


def extract_json(text: str) -> Any:
    """Extract the first JSON object/array from a model response."""
    text = (text or "").strip()
    if not text:
        raise ProviderError("Model returned an empty response", retryable=True)
    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.S | re.I)
    if fenced:
        text = fenced.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Find the outermost {...} or [...]
    starts = [i for i in (text.find("{"), text.find("[")) if i != -1]
    if not starts:
        raise ProviderError("Model response did not contain JSON", retryable=True)
    start = min(starts)
    end = max(text.rfind("}"), text.rfind("]"))
    if end <= start:
        raise ProviderError("Model response contained incomplete JSON", retryable=True)
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ProviderError(f"Invalid JSON from model: {exc}", retryable=True) from exc


def _tokens_from_usage(usage: dict[str, Any] | None) -> tuple[int, int]:
    usage = usage or {}
    prompt = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
    completion = usage.get("completion_tokens") or usage.get("output_tokens") or 0
    return int(prompt or 0), int(completion or 0)


class BaseProvider(abc.ABC):
    """Common interface implemented by every provider adapter."""

    name: str = "base"
    label: str = "Base"
    notes: str = ""

    def __init__(self, config: ProviderConfig, timeout: float = 60.0):
        self.config = config
        self.timeout = timeout

    # -- interface ---------------------------------------------------------
    @abc.abstractmethod
    async def generate(self, request: GatewayRequest) -> GatewayResponse:
        ...

    async def generate_structured(
        self, request: GatewayRequest, schema: type[TModel]
    ) -> TModel:
        """Ask for JSON, parse it, and validate against ``schema``."""
        system = (
            "You are a precise data extraction engine. Reply with a single JSON object only, "
            "with no commentary, no markdown fences and no trailing text. "
            "Follow the requested JSON schema exactly."
        )
        messages = list(request.messages)
        if not messages or messages[0].role != "system":
            messages.insert(0, ChatMessage(role="system", content=system))
        else:
            messages[0] = ChatMessage(role="system", content=system + "\n" + messages[0].content)
        enriched = request.model_copy(update={"messages": messages, "json_mode": True})
        response = await self.generate(enriched)
        data = extract_json(response.content)
        if isinstance(data, list) and hasattr(schema, "model_fields"):
            # Tolerate models that wrap a list in {"items": [...]}
            if "questions" in schema.model_fields:
                data = {"questions": data}
        try:
            return schema.model_validate(data)
        except ValidationError as exc:
            raise ProviderError(
                f"Model output failed schema validation: {exc.errors()[:2]}", retryable=True
            ) from exc

    async def stream(self, request: GatewayRequest) -> AsyncIterator[str]:
        response = await self.generate(request)
        yield response.content

    @abc.abstractmethod
    async def health_check(self) -> ProviderHealth:
        ...

    async def list_models(self) -> list[str]:
        return [self.config.model] if self.config.model else []

    # -- helpers -----------------------------------------------------------
    def _health(self, healthy: bool, detail: str, latency: float = 0.0) -> ProviderHealth:
        return ProviderHealth(
            provider=self.name,
            configured=self.config.configured,
            healthy=healthy,
            detail=detail,
            latency_ms=round(latency, 1),
            model=self.config.model,
        )

    async def _timed(self, coro_factory):
        start = time.perf_counter()
        result = await coro_factory()
        return result, (time.perf_counter() - start) * 1000


class OpenAICompatibleProvider(BaseProvider):
    """Shared implementation for OpenRouter, Groq, Ollama and custom endpoints."""

    extra_headers: dict[str, str] = {}

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", **self.extra_headers}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers

    def _chat_url(self) -> str:
        base = self.config.base_url.rstrip("/")
        return base + "/chat/completions"

    async def generate(self, request: GatewayRequest) -> GatewayResponse:
        if not self.config.configured and self.name != "ollama":
            raise ProviderNotConfigured(self.name)
        payload: dict[str, Any] = {
            "model": request.model or self.config.model,
            "messages": [m.model_dump() for m in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        if request.json_mode:
            payload["response_format"] = {"type": "json_object"}
        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(self._chat_url(), json=payload, headers=self._headers())
                if resp.status_code == 400 and "response_format" in payload:
                    payload.pop("response_format", None)
                    resp = await client.post(
                        self._chat_url(), json=payload, headers=self._headers()
                    )
        except httpx.TimeoutException as exc:
            raise ProviderError(f"{self.name} timed out", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"{self.name} network error: {exc}", retryable=True) from exc
        latency = (time.perf_counter() - start) * 1000
        if resp.status_code >= 400:
            detail = resp.text[:500]
            raise ProviderError(
                f"{self.name} HTTP {resp.status_code}: {detail}",
                retryable=resp.status_code in (408, 409, 429, 500, 502, 503, 504),
                status=resp.status_code,
            )
        try:
            data = resp.json()
            content = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, ValueError) as exc:
            raise ProviderError(f"{self.name} returned an unexpected payload", retryable=True) from exc
        prompt_tokens, completion_tokens = _tokens_from_usage(data.get("usage"))
        return GatewayResponse(
            content=content,
            provider=self.name,
            model=payload["model"],
            latency_ms=round(latency, 1),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            raw=data,
        )

    async def health_check(self) -> ProviderHealth:
        if not self.config.configured and self.name != "ollama":
            return self._health(False, "API key is not set")
        url = self.config.base_url.rstrip("/") + "/models"
        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=min(self.timeout, 12)) as client:
                resp = await client.get(url, headers=self._headers())
            latency = (time.perf_counter() - start) * 1000
            if resp.status_code < 400:
                return self._health(True, "Reachable", latency)
            return self._health(False, f"HTTP {resp.status_code}", latency)
        except httpx.HTTPError as exc:
            return self._health(False, f"Unreachable: {str(exc)[:120]}")

    async def list_models(self) -> list[str]:
        if not self.config.configured and self.name != "ollama":
            return []
        url = self.config.base_url.rstrip("/") + "/models"
        try:
            async with httpx.AsyncClient(timeout=min(self.timeout, 15)) as client:
                resp = await client.get(url, headers=self._headers())
            if resp.status_code >= 400:
                return [self.config.model] if self.config.model else []
            data = resp.json().get("data", [])
            models = sorted({m.get("id", "") for m in data if m.get("id")})
            if self.config.model and self.config.model not in models:
                models.insert(0, self.config.model)
            return models[:200]
        except Exception:
            return [self.config.model] if self.config.model else []


class OpenRouterProvider(OpenAICompatibleProvider):
    name = "openrouter"
    label = "OpenRouter"
    notes = "Free-model router; usage limits apply to free variants."

    def _headers(self) -> dict[str, str]:
        headers = super()._headers()
        headers.setdefault("HTTP-Referer", "http://localhost:5173")
        headers.setdefault("X-Title", "RecruiMate")
        return headers


class GroqProvider(OpenAICompatibleProvider):
    name = "groq"
    label = "Groq"
    notes = "Fast free-tier inference. Rate limited."


class OllamaProvider(OpenAICompatibleProvider):
    name = "ollama"
    label = "Ollama (local)"
    notes = "Local models through the OpenAI-compatible endpoint."

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers


class CustomProvider(OpenAICompatibleProvider):
    name = "custom"
    label = "Custom endpoint"
    notes = "An OpenAI-compatible endpoint on an approved host."


class GeminiProvider(BaseProvider):
    name = "gemini"
    label = "Google Gemini"
    notes = "Uses the Generative Language REST API."

    def _url(self, method: str) -> str:
        base = self.config.base_url.rstrip("/")
        return f"{base}/models/{self.config.model}:{method}?key={self.config.api_key}"

    @staticmethod
    def _to_contents(messages: list[ChatMessage]) -> tuple[list[dict], str]:
        system_parts: list[str] = []
        contents: list[dict] = []
        for m in messages:
            if m.role == "system":
                system_parts.append(m.content)
            else:
                role = "model" if m.role == "assistant" else "user"
                contents.append({"role": role, "parts": [{"text": m.content}]})
        return contents, "\n".join(system_parts)

    async def generate(self, request: GatewayRequest) -> GatewayResponse:
        if not self.config.configured:
            raise ProviderNotConfigured(self.name)
        contents, system = self._to_contents(request.messages)
        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": request.temperature,
                "maxOutputTokens": request.max_tokens,
            },
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        if request.json_mode:
            payload["generationConfig"]["responseMimeType"] = "application/json"
        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(self._url("generateContent"), json=payload)
        except httpx.HTTPError as exc:
            raise ProviderError(f"gemini network error: {exc}", retryable=True) from exc
        latency = (time.perf_counter() - start) * 1000
        if resp.status_code >= 400:
            raise ProviderError(
                f"gemini HTTP {resp.status_code}: {resp.text[:400]}",
                retryable=resp.status_code in (429, 500, 503),
                status=resp.status_code,
            )
        data = resp.json()
        try:
            content = "".join(
                part.get("text", "")
                for part in data["candidates"][0]["content"]["parts"]
            )
        except (KeyError, IndexError) as exc:
            raise ProviderError("gemini returned an unexpected payload", retryable=True) from exc
        usage = data.get("usageMetadata", {})
        return GatewayResponse(
            content=content,
            provider=self.name,
            model=self.config.model,
            latency_ms=round(latency, 1),
            prompt_tokens=int(usage.get("promptTokenCount", 0)),
            completion_tokens=int(usage.get("candidatesTokenCount", 0)),
            raw=data,
        )

    async def health_check(self) -> ProviderHealth:
        if not self.config.configured:
            return self._health(False, "API key is not set")
        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=min(self.timeout, 12)) as client:
                resp = await client.get(
                    f"{self.config.base_url.rstrip('/')}/models?key={self.config.api_key}"
                )
            latency = (time.perf_counter() - start) * 1000
            return self._health(
                resp.status_code < 400,
                "Reachable" if resp.status_code < 400 else f"HTTP {resp.status_code}",
                latency,
            )
        except httpx.HTTPError as exc:
            return self._health(False, f"Unreachable: {str(exc)[:120]}")

    async def list_models(self) -> list[str]:
        if not self.config.configured:
            return []
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{self.config.base_url.rstrip('/')}/models?key={self.config.api_key}"
                )
            if resp.status_code >= 400:
                return [self.config.model]
            names = [
                m.get("name", "").split("/")[-1]
                for m in resp.json().get("models", [])
                if m.get("name")
            ]
            return sorted(set(n for n in names if n))[:200]
        except Exception:
            return [self.config.model]


class OpenCodeProvider(BaseProvider):
    """Adapter for a self-hosted OpenCode *server* session API.

    OpenCode is an agent runtime, so this adapter is deliberately minimal: it
    creates a throwaway session, asks one question, reads the assistant message
    and deletes the session. It never calls ``/v1/chat/completions``.
    """

    name = "opencode"
    label = "OpenCode server"
    notes = "Self-hosted OpenCode session API. Restricted runtime recommended."

    def __init__(self, config: ProviderConfig, timeout: float = 120.0, username: str = "opencode"):
        super().__init__(config, timeout=timeout)
        self.username = username

    def _auth(self) -> tuple[str, str] | None:
        if self.config.api_key:
            return (self.username, self.config.api_key)
        return None

    def _url(self, path: str) -> str:
        base = self.config.base_url.rstrip("/")
        if base.endswith("/api"):
            return base + path
        return base + path

    async def _delete_session(self, client: httpx.AsyncClient, session_id: str) -> None:
        try:
            await client.delete(self._url(f"/session/{session_id}"))
        except Exception:
            pass

    async def generate(self, request: GatewayRequest) -> GatewayResponse:
        if not self.config.configured:
            raise ProviderNotConfigured(self.name)
        prompt = "\n\n".join(f"{m.role.upper()}: {m.content}" for m in request.messages)
        start = time.perf_counter()
        async with httpx.AsyncClient(
            timeout=self.timeout, auth=self._auth(), headers={"Content-Type": "application/json"}
        ) as client:
            try:
                created = await client.post(self._url("/session"), json={"title": "RecruiMate"})
                if created.status_code >= 400:
                    raise ProviderError(
                        f"opencode session create HTTP {created.status_code}: {created.text[:300]}",
                        retryable=created.status_code >= 500,
                    )
                session_id = created.json().get("id")
                if not session_id:
                    raise ProviderError("opencode did not return a session id")
                body = {
                    "parts": [{"type": "text", "text": prompt}],
                    "system": "You are a precise assistant inside RecruiMate. Reply in the requested format only.",
                    "tools": {},
                }
                if self.config.model and self.config.model != "opencode":
                    provider_id, _, model_id = self.config.model.partition("/")
                    if model_id:
                        body["model"] = {"providerID": provider_id, "modelID": model_id}
                posted = await client.post(
                    self._url(f"/session/{session_id}/message"), json=body
                )
                if posted.status_code >= 400:
                    raise ProviderError(
                        f"opencode prompt HTTP {posted.status_code}: {posted.text[:300]}",
                        retryable=posted.status_code >= 500,
                    )
                content = self._extract_text(posted.json())
                # Some server versions answer asynchronously; poll message history.
                if not content:
                    import asyncio

                    for _ in range(60):
                        await asyncio.sleep(0.5)
                        history = await client.get(self._url(f"/session/{session_id}/message"))
                        if history.status_code < 400:
                            content = self._extract_text(history.json(), prefer_last=True)
                            if content:
                                break
                await self._delete_session(client, session_id)
            except httpx.HTTPError as exc:
                raise ProviderError(f"opencode network error: {exc}", retryable=True) from exc
        latency = (time.perf_counter() - start) * 1000
        if not content:
            raise ProviderError("opencode returned no assistant text", retryable=True)
        return GatewayResponse(
            content=content,
            provider=self.name,
            model=self.config.model,
            latency_ms=round(latency, 1),
        )

    @staticmethod
    def _extract_text(payload: Any, prefer_last: bool = False) -> str:
        """Handle both a single message and a list of messages."""
        def message_text(msg: Any) -> str:
            if isinstance(msg, dict):
                info = msg.get("info") or {}
                if info.get("role") and info.get("role") != "assistant":
                    return ""
                parts = msg.get("parts") or []
                texts = [
                    p.get("text", "")
                    for p in parts
                    if isinstance(p, dict) and p.get("type", "text") == "text"
                ]
                if texts:
                    return "".join(texts)
                return msg.get("content", "") if isinstance(msg.get("content"), str) else ""
            return ""

        if isinstance(payload, list):
            candidates = [message_text(m) for m in payload]
            candidates = [c for c in candidates if c]
            return (candidates[-1] if prefer_last else candidates[-1]) if candidates else ""
        if isinstance(payload, dict):
            text = message_text(payload)
            if text:
                return text
            for key in ("messages", "data", "result"):
                if isinstance(payload.get(key), list):
                    return OpenCodeProvider._extract_text(payload[key], prefer_last)
            parts = payload.get("parts") or []
            return "".join(
                p.get("text", "") for p in parts if isinstance(p, dict) and "text" in p
            )
        return ""

    async def health_check(self) -> ProviderHealth:
        if not self.config.configured:
            return self._health(False, "Server URL/password not set")
        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=8, auth=self._auth()) as client:
                resp = await client.get(self._url("/session"))
            latency = (time.perf_counter() - start) * 1000
            return self._health(
                resp.status_code < 400,
                "Reachable" if resp.status_code < 400 else f"HTTP {resp.status_code}",
                latency,
            )
        except httpx.HTTPError as exc:
            return self._health(False, f"Unreachable: {str(exc)[:120]}")

    async def list_models(self) -> list[str]:
        try:
            async with httpx.AsyncClient(timeout=10, auth=self._auth()) as client:
                resp = await client.get(self._url("/config/providers"))
            if resp.status_code < 400:
                data = resp.json()
                providers = data.get("providers", data) if isinstance(data, dict) else data
                models: list[str] = []
                if isinstance(providers, list):
                    for p in providers:
                        pid = p.get("id", "")
                        for m in p.get("models", {}).keys() if isinstance(p.get("models"), dict) else []:
                            models.append(f"{pid}/{m}")
                if models:
                    return models[:200]
        except Exception:
            pass
        return [self.config.model] if self.config.model else []


class HeuristicProvider(BaseProvider):
    """Offline provider marker — agents never call it for text generation.

    It exists so the gateway can report a healthy, always-available option and
    so provider settings have a consistent shape. Real analysis without an LLM is
    performed by deterministic agent logic, not by this class.
    """

    name = "heuristic"
    label = "Local heuristics"
    notes = "No API key. Deterministic extraction and scoring; no text generation."

    async def generate(self, request: GatewayRequest) -> GatewayResponse:
        raise ProviderNotConfigured(self.name)

    async def health_check(self) -> ProviderHealth:
        return self._health(True, "Always available (no LLM calls)")
