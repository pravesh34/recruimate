"""Shared agent plumbing: provider-aware structured generation with graceful degradation."""
from __future__ import annotations

import logging

from pydantic import ValidationError

from ..gateway import AllProvidersFailed, GatewayManager, ProviderError
from ..gateway.base import extract_json
from ..schemas import GatewayRequest
from ..services.embedding_service import get_embedding_service

logger = logging.getLogger("recruimate.agents")


class BaseAgent:
    name = "base_agent"
    label = "Base agent"

    def __init__(self, gateway: GatewayManager):
        self.gateway = gateway
        self.embeddings = get_embedding_service()

    @property
    def llm_enabled(self) -> bool:
        try:
            return self.gateway.llm_available(self.name)
        except Exception:
            return False

    def provider_label(self) -> str:
        try:
            provider, _ = self.gateway.resolve(self.name)
            return provider
        except Exception:
            return "heuristic"

    async def _generate(
        self,
        prompt: str,
        schema,
        *,
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2200,
    ):
        """Return (validated_model | None, provider_name, error_message)."""
        if not self.llm_enabled:
            return None, "heuristic", ""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        request = GatewayRequest(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=True,
            agent=self.name,
        )
        try:
            response = await self.gateway.generate(request, agent=self.name)
        except AllProvidersFailed as exc:
            logger.warning("%s: all providers failed: %s", self.name, exc)
            return None, "heuristic", str(exc)
        except (ProviderError, Exception) as exc:  # pragma: no cover - defensive
            logger.warning("%s: generation failed: %s", self.name, exc)
            return None, "heuristic", str(exc)

        try:
            data = extract_json(response.content)
            if isinstance(data, list) and "questions" in getattr(schema, "model_fields", {}):
                data = {"questions": data}
            return schema.model_validate(data), response.provider, ""
        except (ProviderError, ValidationError, ValueError) as exc:
            logger.warning("%s: invalid structured output: %s", self.name, exc)
            return None, response.provider, f"Structured output rejected: {exc}"

    @staticmethod
    def _union(*lists: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for items in lists:
            for item in items or []:
                key = item.strip().lower()
                if key and key not in seen:
                    seen.add(key)
                    out.append(item.strip())
        return out
