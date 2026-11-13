"""Daily AI request budget.

The gateway enforces a per-user, per-UTC-day cap on successful LLM calls.
Once the cap is hit it raises :class:`DailyBudgetExceeded` (which agents
translate into a graceful fallback to heuristic mode) and records a
``status="budget"`` usage row. ``ai_daily_request_limit = 0`` disables it.
"""
from __future__ import annotations

import uuid

import pytest
from pydantic import BaseModel

from app.config import settings
from app.database.models import ProviderConfiguration, SessionLocal, UsageLog, User, init_db
from app.gateway import DailyBudgetExceeded, GatewayManager
from app.schemas import GatewayRequest, GatewayResponse


@pytest.fixture(scope="module", autouse=True)
def _database():
    init_db()


class _StubProvider:
    """Pretends to be any real provider; always answers."""

    def __init__(self, config):
        self.config = config

    async def generate(self, request: GatewayRequest) -> GatewayResponse:
        return GatewayResponse(
            content='{"ok": true}',
            provider=self.config.provider,
            model=self.config.model,
        )


@pytest.fixture()
def budget_user():
    with SessionLocal() as db:
        user = User(email=f"budget-{uuid.uuid4().hex[:10]}@example.com", display_name="Budget")
        db.add(user)
        db.commit()
        db.refresh(user)
        db.add(
            ProviderConfiguration(
                user_id=user.id,
                provider="groq",
                enabled=True,
                api_key="test-key",
                base_url=settings.groq_base_url,
                model="test-model",
            )
        )
        db.commit()
        yield user.id
        # Cleanup happens with the test DB lifecycle; rows are isolated per run.


def _gateway(user_id: int) -> GatewayManager:
    db = SessionLocal()
    manager = GatewayManager(db, user_id=user_id)
    manager.routing = {"default_provider": "groq", "agent_overrides": {}}
    manager.provider_instance = lambda name, cfg=None: _StubProvider(cfg or manager.configs[name])
    return manager


def _request() -> GatewayRequest:
    return GatewayRequest(messages=[{"role": "user", "content": "hi"}])


def test_budget_blocks_after_limit_and_logs(budget_user, monkeypatch):
    monkeypatch.setattr(settings, "ai_daily_request_limit", 2)
    manager = _gateway(budget_user)

    import asyncio

    first = asyncio.run(manager.generate(_request()))
    second = asyncio.run(manager.generate(_request()))
    assert first.content == '{"ok": true}'
    assert second.content == '{"ok": true}'

    with pytest.raises(DailyBudgetExceeded):
        asyncio.run(manager.generate(_request()))

    with SessionLocal() as db:
        blocked = (
            db.query(UsageLog)
            .filter(UsageLog.user_id == budget_user, UsageLog.status == "budget")
            .count()
        )
        ok = (
            db.query(UsageLog)
            .filter(UsageLog.user_id == budget_user, UsageLog.status == "ok")
            .count()
        )
    assert blocked == 1
    assert ok == 2


def test_budget_disabled_when_zero(budget_user, monkeypatch):
    monkeypatch.setattr(settings, "ai_daily_request_limit", 0)
    manager = _gateway(budget_user)
    import asyncio

    for _ in range(5):
        response = asyncio.run(manager.generate(_request()))
        assert response.content == '{"ok": true}'


def test_agents_degrade_gracefully_on_budget_block(budget_user, monkeypatch):
    """An agent whose provider budget is exhausted falls back to heuristics."""
    import asyncio

    from app.agents.base import BaseAgent

    monkeypatch.setattr(settings, "ai_daily_request_limit", 1)
    manager = _gateway(budget_user)

    class Echo(BaseAgent):
        name = "supervisor"

    asyncio.run(manager.generate(_request()))  # burn the day's budget

    agent = Echo(manager)
    payload, provider, warning = asyncio.run(
        agent._generate('{"n": 1}', _EchoSchema, system="be brief")
    )
    assert payload is None
    assert "budget" in warning.lower()


class _EchoSchema(BaseModel):
    ok: bool
