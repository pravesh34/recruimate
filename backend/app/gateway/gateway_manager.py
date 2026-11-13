"""Unified LLM gateway: configuration, routing, retries, fallback and usage logs."""
from __future__ import annotations

import asyncio
import datetime as dt
import ipaddress
import time
from dataclasses import replace
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import settings
from ..database.models import AppSetting, ProviderConfiguration, UsageLog, ensure_default_user
from ..schemas import GatewayRequest, GatewayResponse, ProviderHealth, ProviderInfo
from .base import (
    BaseProvider,
    CustomProvider,
    GeminiProvider,
    GroqProvider,
    HeuristicProvider,
    OllamaProvider,
    OpenCodeProvider,
    OpenRouterProvider,
    ProviderConfig,
    ProviderError,
    ProviderNotConfigured,
)
from .fallback import DEFAULT_FALLBACK_ORDER, fallback_candidates

PROVIDER_LABELS = {
    "heuristic": "Local heuristics",
    "openrouter": "OpenRouter",
    "groq": "Groq",
    "gemini": "Google Gemini",
    "opencode": "OpenCode server",
    "ollama": "Ollama (local)",
    "custom": "Custom endpoint",
}

PROVIDER_NOTES = {
    "heuristic": "Offline mode. Deterministic analysis, no external calls, no API key.",
    "openrouter": "One key, many models. Free router available; rate limits apply.",
    "groq": "Free-tier fast inference. Good for structured extraction.",
    "gemini": "Google AI Studio free tier. JSON output supported.",
    "opencode": "Your self-hosted OpenCode session API. Restricted runtime recommended.",
    "ollama": "Local inference on your machine. No data leaves your device.",
    "custom": "Any OpenAI-compatible endpoint on an approved host.",
}

KNOWN_HOSTS = {
    "openrouter": {"openrouter.ai"},
    "groq": {"api.groq.com"},
    "gemini": {"generativelanguage.googleapis.com"},
}

DEFAULT_MODELS = {
    "openrouter": settings.openrouter_model,
    "groq": settings.groq_model,
    "gemini": settings.gemini_model,
    "opencode": settings.opencode_model,
    "ollama": settings.ollama_model,
    "custom": "",
}

ALL_PROVIDERS = list(PROVIDER_LABELS)


class AllProvidersFailed(ProviderError):
    def __init__(self, attempts: list[str]):
        super().__init__("All configured providers failed: " + " | ".join(attempts), retryable=False)
        self.attempts = attempts


class DailyBudgetExceeded(ProviderError):
    """Raised instead of making LLM calls once the user's daily cap is hit."""

    def __init__(self, provider: str, limit: int):
        super().__init__(
            f"Daily AI request budget of {limit} reached; falling back to heuristics",
            retryable=False,
        )
        self.provider = provider
        self.limit = limit


def validate_base_url(url: str, provider: str) -> str:
    """Validate provider URLs and block obvious SSRF targets."""
    url = (url or "").strip().rstrip("/")
    if not url:
        raise ValueError("Base URL is required")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Base URL must use http or https")
    if not parsed.hostname:
        raise ValueError("Base URL must include a hostname")
    host = parsed.hostname.lower()
    # Cloud metadata endpoints are never allowed.
    if host in {"169.254.169.254", "metadata.google.internal"}:
        raise ValueError("This host is not permitted")
    if provider in KNOWN_HOSTS:
        allowed = KNOWN_HOSTS[provider]
        if host not in allowed and not host.endswith(".openrouter.ai"):
            raise ValueError(
                f"{provider} base URL must point to an official host ({', '.join(sorted(allowed))})"
            )
    if provider == "custom":
        allowed_custom = {
            h.strip().lower() for h in settings.allowed_custom_hosts.split(",") if h.strip()
        }
        if host not in allowed_custom:
            raise ValueError(
                "Custom endpoint host is not approved. Add it to ALLOWED_CUSTOM_HOSTS."
            )
    if provider in {"opencode", "ollama"}:
        try:
            ip = ipaddress.ip_address(host)
            if ip.is_link_local:
                raise ValueError("Link-local hosting is not permitted")
        except ValueError as exc:
            if "Link-local" in str(exc):
                raise
    return url


def build_config(provider: str, db_row: ProviderConfiguration | None = None) -> ProviderConfig:
    """Merge environment defaults with the user's stored configuration."""
    from . import env_defaults

    defaults = env_defaults(provider)
    if db_row is None:
        return defaults
    return ProviderConfig(
        provider=provider,
        api_key=db_row.api_key or defaults.api_key,
        base_url=db_row.base_url or defaults.base_url,
        model=db_row.model or defaults.model,
        temperature=db_row.temperature,
        max_tokens=db_row.max_tokens,
        is_paid=db_row.is_paid,
        enabled=db_row.enabled,
        agent_overrides=db_row.agent_overrides or {},
    )


class GatewayManager:
    def __init__(self, db: Session, user_id: int | None = None):
        self.db = db
        self.user = ensure_default_user(db)
        self.user_id = user_id or self.user.id
        self.configs = self._load_configs()
        self.routing = self._load_routing()

    # ------------------------------------------------------------------ setup
    def _load_configs(self) -> dict[str, ProviderConfig]:
        rows = {
            r.provider: r
            for r in self.db.query(ProviderConfiguration)
            .filter(ProviderConfiguration.user_id == self.user_id)
            .all()
        }
        return {name: build_config(name, rows.get(name)) for name in ALL_PROVIDERS}

    def _load_routing(self) -> dict[str, Any]:
        row = self.db.get(AppSetting, "routing")
        if not row or not isinstance(row.value, dict):
            return {"default_provider": settings.default_provider, "agent_overrides": {}}
        routing = row.value
        routing.setdefault("default_provider", settings.default_provider)
        routing.setdefault("agent_overrides", {})
        return routing

    def save_routing(self, routing: dict[str, Any]) -> None:
        row = self.db.get(AppSetting, "routing")
        if row:
            row.value = routing
        else:
            self.db.add(AppSetting(key="routing", value=routing))
        self.db.commit()
        self.routing = routing

    def ensure_rows(self) -> None:
        existing = {
            r.provider
            for r in self.db.query(ProviderConfiguration)
            .filter(ProviderConfiguration.user_id == self.user_id)
            .all()
        }
        changed = False
        for name in ALL_PROVIDERS:
            if name in existing:
                continue
            cfg = build_config(name)
            self.db.add(
                ProviderConfiguration(
                    user_id=self.user_id,
                    provider=name,
                    enabled=cfg.enabled if name != "heuristic" else True,
                    api_key="",
                    base_url="",
                    model="",
                    is_paid=False,
                )
            )
            changed = True
        if changed:
            self.db.commit()

    def update_config(self, provider: str, payload: dict[str, Any]) -> ProviderInfo:
        if provider not in ALL_PROVIDERS:
            raise ValueError(f"Unknown provider '{provider}'")
        self.ensure_rows()
        row = (
            self.db.query(ProviderConfiguration)
            .filter_by(user_id=self.user_id, provider=provider)
            .first()
        )
        if not row:
            raise ValueError("Provider configuration not found")

        base_url = payload.get("base_url", row.base_url) or ""
        if base_url:
            validate_base_url(base_url, provider)
        api_key = payload.get("api_key")
        if api_key is not None and api_key.strip():
            row.api_key = api_key.strip()
        if base_url:
            row.base_url = base_url
        if payload.get("model") is not None:
            row.model = str(payload["model"]).strip()
        if payload.get("temperature") is not None:
            row.temperature = float(payload["temperature"])
        if payload.get("max_tokens") is not None:
            row.max_tokens = int(payload["max_tokens"])
        if payload.get("enabled") is not None:
            row.enabled = bool(payload["enabled"])
        if payload.get("is_paid") is not None:
            row.is_paid = bool(payload["is_paid"])
        if payload.get("agent_overrides") is not None:
            row.agent_overrides = payload["agent_overrides"]
        if payload.get("default_provider"):
            routing = dict(self.routing)
            routing["default_provider"] = payload["default_provider"]
            self.save_routing(routing)
        if payload.get("clear_api_key"):
            row.api_key = ""
        self.db.commit()
        self.configs = self._load_configs()
        return self.provider_info(provider)

    def add_custom_provider(self, name: str, base_url: str, api_key: str, model: str) -> None:
        """Custom providers share the 'custom' adapter but can be named individually."""
        validate_base_url(base_url, "custom")
        self.update_config(
            "custom",
            {
                "enabled": True,
                "base_url": base_url,
                "api_key": api_key,
                "model": model,
            },
        )

    # ---------------------------------------------------------------- routing
    def resolve(self, agent: str) -> tuple[str, ProviderConfig]:
        overrides = self.routing.get("agent_overrides", {})
        override = overrides.get(agent) or {}
        provider = override.get("provider") or self.routing.get(
            "default_provider", settings.default_provider
        )
        if provider not in self.configs:
            provider = settings.default_provider
        cfg = self.configs[provider]
        if override.get("model"):
            cfg = replace(cfg, model=override["model"])
        return provider, cfg

    def set_agent_override(self, agent: str, provider: str | None, model: str | None) -> None:
        routing = dict(self.routing)
        overrides = dict(routing.get("agent_overrides", {}))
        if not provider:
            overrides.pop(agent, None)
        else:
            if provider not in ALL_PROVIDERS:
                raise ValueError(f"Unknown provider '{provider}'")
            overrides[agent] = {"provider": provider, "model": model or ""}
        routing["agent_overrides"] = overrides
        self.save_routing(routing)

    def llm_available(self, agent: str) -> bool:
        provider, cfg = self.resolve(agent)
        return provider != "heuristic" and cfg.enabled and cfg.configured

    def _budget_exhausted(self) -> bool:
        """True when the caller already made the day's allowed LLM requests.

        Counts successful calls (``UsageLog.status == "ok"``) since midnight UTC
        for this user. ``ai_daily_request_limit = 0`` disables the cap.
        """
        limit = settings.ai_daily_request_limit
        if limit <= 0:
            return False
        day_start = dt.datetime.now(dt.timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        used = (
            self.db.query(func.count(UsageLog.id))
            .filter(UsageLog.user_id == self.user_id)
            .filter(UsageLog.status == "ok")
            .filter(UsageLog.created_at >= day_start)
            .scalar()
            or 0
        )
        return used >= limit

    # -------------------------------------------------------------- providers
    def provider_instance(self, name: str, cfg: ProviderConfig | None = None) -> BaseProvider:
        cfg = cfg or self.configs.get(name)
        if not cfg:
            raise ValueError(f"Unknown provider '{name}'")
        if name == "heuristic":
            return HeuristicProvider(cfg)
        if name == "openrouter":
            return OpenRouterProvider(cfg, timeout=settings.request_timeout)
        if name == "groq":
            return GroqProvider(cfg, timeout=settings.request_timeout)
        if name == "gemini":
            return GeminiProvider(cfg, timeout=settings.request_timeout)
        if name == "ollama":
            return OllamaProvider(cfg, timeout=settings.request_timeout)
        if name == "custom":
            return CustomProvider(cfg, timeout=settings.request_timeout)
        if name == "opencode":
            return OpenCodeProvider(
                cfg, timeout=max(settings.request_timeout, 120), username=settings.opencode_username
            )
        raise ValueError(f"Unknown provider '{name}'")

    # -------------------------------------------------------------- generate
    async def generate(self, request: GatewayRequest, agent: str = "supervisor") -> GatewayResponse:
        primary, cfg = self.resolve(agent)
        if request.model is None:
            request = request.model_copy(update={"model": cfg.model})
        if primary == "heuristic" or not cfg.enabled or not cfg.configured:
            raise ProviderNotConfigured(primary)
        if self._budget_exhausted():
            self._log(
                provider=primary,
                model=cfg.model,
                agent=agent,
                status="budget",
                error=f"Daily AI budget of {settings.ai_daily_request_limit} reached",
            )
            raise DailyBudgetExceeded(primary, settings.ai_daily_request_limit)

        candidates = [cfg] + fallback_candidates(
            self.configs, primary, allow_paid=settings.allow_paid_fallback
        )
        attempts: list[str] = []
        for candidate in candidates:
            provider = self.provider_instance(candidate.provider, candidate)
            for attempt in range(settings.max_retries + 1):
                try:
                    started = time.perf_counter()
                    response = await provider.generate(
                        request.model_copy(update={"model": request.model or candidate.model})
                    )
                    self._log(
                        provider=candidate.provider,
                        model=response.model,
                        agent=agent,
                        status="ok",
                        latency=response.latency_ms,
                        prompt_tokens=response.prompt_tokens,
                        completion_tokens=response.completion_tokens,
                    )
                    return response
                except ProviderError as exc:
                    attempts.append(f"{candidate.provider}: {exc}")
                    if exc.retryable and attempt < settings.max_retries and exc.status != 429:
                        await asyncio.sleep(0.6 * (attempt + 1))
                        continue
                    if exc.retryable and exc.status == 429 and attempt < settings.max_retries:
                        await asyncio.sleep(1.5 * (attempt + 1))
                        continue
                    break
                except Exception as exc:  # provider bug must not break the agent
                    attempts.append(f"{candidate.provider}: unexpected {exc}")
                    break
        raise AllProvidersFailed(attempts)

    def _log(
        self,
        *,
        provider: str,
        model: str,
        agent: str,
        status: str,
        latency: float = 0.0,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        error: str = "",
    ) -> None:
        try:
            self.db.add(
                UsageLog(
                    user_id=self.user_id,
                    provider=provider,
                    model=model[:255],
                    agent=agent,
                    status=status,
                    latency_ms=latency,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    error=error[:1000],
                )
            )
            self.db.commit()
        except Exception:
            self.db.rollback()

    # ----------------------------------------------------------------- health
    async def health(self, provider: str) -> ProviderHealth:
        if provider == "heuristic":
            return ProviderHealth(provider=provider, configured=True, healthy=True, detail="Always available")
        cfg = self.configs.get(provider)
        if not cfg:
            raise ValueError(f"Unknown provider '{provider}'")
        try:
            return await self.provider_instance(provider, cfg).health_check()
        except Exception as exc:
            return ProviderHealth(
                provider=provider,
                configured=cfg.configured,
                healthy=False,
                detail=str(exc)[:200],
                model=cfg.model,
            )

    async def models(self, provider: str) -> list[str]:
        cfg = self.configs.get(provider)
        if not cfg:
            raise ValueError(f"Unknown provider '{provider}'")
        return await self.provider_instance(provider, cfg).list_models()

    async def test_provider(self, provider: str, model: str | None = None) -> dict[str, Any]:
        cfg = self.configs.get(provider)
        if not cfg:
            raise ValueError(f"Unknown provider '{provider}'")
        if provider == "heuristic":
            return {
                "provider": provider,
                "healthy": True,
                "detail": "Local heuristics require no credentials.",
                "latency_ms": 0,
                "reply": "",
            }
        request = GatewayRequest(
            messages=[
                {"role": "system", "content": "Reply with the single word: ready"},
                {"role": "user", "content": "Connection test"},
            ],
            model=model or cfg.model,
            max_tokens=16,
            temperature=0,
        )
        start = time.perf_counter()
        try:
            response = await self.provider_instance(provider, cfg).generate(request)
            latency = (time.perf_counter() - start) * 1000
            return {
                "provider": provider,
                "healthy": True,
                "detail": "Connection successful",
                "latency_ms": round(latency, 1),
                "reply": response.content[:300],
                "model": response.model,
            }
        except ProviderError as exc:
            return {
                "provider": provider,
                "healthy": False,
                "detail": str(exc)[:400],
                "latency_ms": round((time.perf_counter() - start) * 1000, 1),
                "reply": "",
                "model": model or cfg.model,
            }

    def provider_info(self, provider: str, health: ProviderHealth | None = None) -> ProviderInfo:
        cfg = self.configs.get(provider) or build_config(provider)
        key = cfg.api_key
        hint = ""
        if key:
            hint = f"••••{key[-4:]}" if len(key) > 4 else "••••"
        return ProviderInfo(
            provider=provider,
            label=PROVIDER_LABELS.get(provider, provider),
            enabled=cfg.enabled or provider == "heuristic",
            configured=cfg.configured,
            base_url=cfg.base_url,
            model=cfg.model,
            is_paid=cfg.is_paid,
            api_key_set=bool(key),
            api_key_hint=hint,
            health=health,
            note=PROVIDER_NOTES.get(provider, ""),
        )

    def list_provider_info(self) -> list[ProviderInfo]:
        return [self.provider_info(p) for p in ALL_PROVIDERS]

    def routing_info(self) -> dict[str, Any]:
        return self.routing
