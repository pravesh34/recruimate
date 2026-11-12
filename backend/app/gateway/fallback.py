"""Fallback policy helpers.

The policy is intentionally conservative: a failing free provider may fall back
to another *explicitly enabled* provider, but never silently to a paid model.
"""
from __future__ import annotations

from .base import ProviderConfig


DEFAULT_FALLBACK_ORDER = ["openrouter", "groq", "gemini", "opencode", "ollama", "custom"]


def fallback_candidates(
    configs: dict[str, ProviderConfig],
    primary: str,
    *,
    allow_paid: bool,
) -> list[ProviderConfig]:
    candidates: list[ProviderConfig] = []
    for name in DEFAULT_FALLBACK_ORDER:
        cfg = configs.get(name)
        if not cfg or name == primary:
            continue
        if not (cfg.enabled and cfg.configured):
            continue
        if cfg.is_paid and not allow_paid:
            continue
        candidates.append(cfg)
    return candidates
