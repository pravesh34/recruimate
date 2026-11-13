"""Provider configuration, health, model discovery and routing."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..config import settings
from ..database.models import UsageLog, get_db
from ..gateway import ALL_PROVIDERS, GatewayManager
from ..gateway.fallback import DEFAULT_FALLBACK_ORDER
from ..services.embedding_service import get_embedding_service
from .deps import get_current_user, get_gateway, iso
from .schemas import ProviderConfigBody, ProviderTestRequest, RoutingUpdateRequest

router = APIRouter(prefix="/api/providers", tags=["providers"])

AGENTS = [
    {"id": "resume_agent", "label": "Resume Intelligence", "recommended": "Fast structured-output model"},
    {"id": "job_agent", "label": "Job Intelligence", "recommended": "Fast instruction-following model"},
    {"id": "compatibility_agent", "label": "Compatibility", "recommended": "Deterministic — no LLM required"},
    {"id": "gap_analysis_agent", "label": "Skill Gap Analysis", "recommended": "Deterministic — no LLM required"},
    {"id": "interview_agent", "label": "Interview Preparation", "recommended": "Strong conversational model"},
    {"id": "supervisor", "label": "Supervisor", "recommended": "Orchestration — inherits default provider"},
]


@router.get("")
def list_providers(db: Session = Depends(get_db), gateway: GatewayManager = Depends(get_gateway)):
    gateway.ensure_rows()
    gateway.configs = gateway._load_configs()
    return {
        "providers": [p.model_dump() for p in gateway.list_provider_info()],
        "routing": gateway.routing_info(),
        "agents": AGENTS,
        "fallback_order": DEFAULT_FALLBACK_ORDER,
        "allow_paid_fallback": settings.allow_paid_fallback,
        "embeddings": get_embedding_service().name,
        "security_note": (
            "API keys are stored server-side only and are never returned to the browser. "
            "Custom endpoints are restricted to approved hosts."
        ),
    }


@router.get("/health")
async def provider_health(gateway: GatewayManager = Depends(get_gateway)):
    results = await asyncio.gather(
        *[gateway.health(name) for name in ALL_PROVIDERS], return_exceptions=True
    )
    payload = []
    for name, result in zip(ALL_PROVIDERS, results):
        if isinstance(result, BaseException):
            payload.append(
                {
                    "provider": name,
                    "configured": False,
                    "healthy": False,
                    "detail": str(result)[:200],
                    "latency_ms": 0,
                    "model": "",
                }
            )
        else:
            payload.append(result.model_dump())
    return {"providers": payload}


@router.post("/test")
async def test_provider(payload: ProviderTestRequest, gateway: GatewayManager = Depends(get_gateway)):
    if payload.provider not in ALL_PROVIDERS:
        raise HTTPException(404, f"Unknown provider '{payload.provider}'")
    result = await gateway.test_provider(payload.provider, payload.model)
    gateway._log(
        provider=payload.provider,
        model=payload.model or gateway.configs[payload.provider].model,
        agent="connection_test",
        status="ok" if result.get("healthy") else "error",
        latency=result.get("latency_ms", 0),
        error="" if result.get("healthy") else result.get("detail", ""),
    )
    return result


@router.get("/models")
async def provider_models(
    provider: str = Query(...), gateway: GatewayManager = Depends(get_gateway)
):
    if provider not in ALL_PROVIDERS:
        raise HTTPException(404, f"Unknown provider '{provider}'")
    try:
        models = await gateway.models(provider)
    except Exception as exc:
        raise HTTPException(422, f"Could not list models: {exc}") from exc
    return {"provider": provider, "models": models}


@router.put("/configuration")
def update_configuration(
    payload: ProviderConfigBody,
    db: Session = Depends(get_db),
    gateway: GatewayManager = Depends(get_gateway),
):
    if payload.provider not in ALL_PROVIDERS:
        raise HTTPException(404, f"Unknown provider '{payload.provider}'")
    try:
        info = gateway.update_config(payload.provider, payload.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"provider": info.model_dump(), "routing": gateway.routing_info()}


@router.put("/routing")
def update_routing(payload: RoutingUpdateRequest, gateway: GatewayManager = Depends(get_gateway)):
    routing = dict(gateway.routing_info())
    if payload.default_provider:
        if payload.default_provider not in ALL_PROVIDERS:
            raise HTTPException(400, f"Unknown provider '{payload.default_provider}'")
        routing["default_provider"] = payload.default_provider
    if payload.agent_overrides is not None:
        for agent, override in payload.agent_overrides.items():
            if agent not in {a["id"] for a in AGENTS}:
                raise HTTPException(400, f"Unknown agent '{agent}'")
            provider = (override or {}).get("provider", "")
            if provider and provider not in ALL_PROVIDERS:
                raise HTTPException(400, f"Unknown provider '{provider}'")
        routing["agent_overrides"] = payload.agent_overrides
    gateway.save_routing(routing)
    return {"routing": gateway.routing_info()}


@router.get("/usage")
def provider_usage(
    limit: int = 50,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    rows = (
        db.query(UsageLog)
        .filter(UsageLog.user_id == user.id)
        .order_by(UsageLog.created_at.desc(), UsageLog.id.desc())
        .limit(min(limit, 200))
        .all()
    )
    summary: dict[str, dict] = {}
    for row in rows:
        entry = summary.setdefault(
            row.provider or "unknown", {"requests": 0, "errors": 0, "tokens": 0, "latency_total": 0.0}
        )
        entry["requests"] += 1
        entry["errors"] += 1 if row.status != "ok" else 0
        entry["tokens"] += (row.prompt_tokens or 0) + (row.completion_tokens or 0)
        entry["latency_total"] += row.latency_ms or 0
    return {
        "summary": [
            {
                "provider": provider,
                "requests": data["requests"],
                "errors": data["errors"],
                "tokens": data["tokens"],
                "avg_latency_ms": round(data["latency_total"] / data["requests"], 1),
            }
            for provider, data in summary.items()
        ],
        "logs": [
            {
                "id": r.id,
                "provider": r.provider,
                "model": r.model,
                "agent": r.agent,
                "status": r.status,
                "latency_ms": r.latency_ms,
                "prompt_tokens": r.prompt_tokens,
                "completion_tokens": r.completion_tokens,
                "created_at": iso(r.created_at),
            }
            for r in rows
        ],
    }
