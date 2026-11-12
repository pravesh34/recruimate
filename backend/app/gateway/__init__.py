"""Unified LLM gateway package."""
from __future__ import annotations

from ..config import settings
from .base import (
    BaseProvider,
    ProviderConfig,
    ProviderError,
    ProviderNotConfigured,
)
from .gateway_manager import (
    ALL_PROVIDERS,
    PROVIDER_LABELS,
    AllProvidersFailed,
    GatewayManager,
    validate_base_url,
)

__all__ = [
    "BaseProvider",
    "ProviderConfig",
    "ProviderError",
    "ProviderNotConfigured",
    "GatewayManager",
    "AllProvidersFailed",
    "ALL_PROVIDERS",
    "PROVIDER_LABELS",
    "validate_base_url",
    "env_defaults",
]


def env_defaults(provider: str) -> ProviderConfig:
    if provider == "heuristic":
        return ProviderConfig(provider="heuristic", enabled=True)
    if provider == "openrouter":
        return ProviderConfig(
            provider="openrouter",
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            model=settings.openrouter_model,
            enabled=bool(settings.openrouter_api_key),
            is_paid=False,
        )
    if provider == "groq":
        return ProviderConfig(
            provider="groq",
            api_key=settings.groq_api_key,
            base_url=settings.groq_base_url,
            model=settings.groq_model,
            enabled=bool(settings.groq_api_key),
        )
    if provider == "gemini":
        return ProviderConfig(
            provider="gemini",
            api_key=settings.gemini_api_key,
            base_url=settings.gemini_base_url,
            model=settings.gemini_model,
            enabled=bool(settings.gemini_api_key),
        )
    if provider == "opencode":
        return ProviderConfig(
            provider="opencode",
            api_key=settings.opencode_password,
            base_url=settings.opencode_base_url,
            model=settings.opencode_model,
            enabled=bool(settings.opencode_password) or settings.opencode_base_url != "http://127.0.0.1:8080",
        )
    if provider == "ollama":
        return ProviderConfig(
            provider="ollama",
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            enabled=False,
        )
    if provider == "custom":
        return ProviderConfig(provider="custom", enabled=False)
    raise ValueError(f"Unknown provider '{provider}'")
