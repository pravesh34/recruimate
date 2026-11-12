"""API dependencies and shared serialisation helpers."""
from __future__ import annotations

import datetime as dt
from typing import Any

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from ..config import settings
from ..database.models import get_db
from ..gateway import GatewayManager


async def require_auth(authorization: str | None = Header(default=None)) -> None:
    """Optional bearer auth. Empty API_TOKEN means trusted local mode."""
    if not settings.api_token:
        return
    expected = f"Bearer {settings.api_token}"
    if authorization != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_gateway(db: Session = Depends(get_db)) -> GatewayManager:
    return GatewayManager(db)


def iso(value: dt.datetime | None) -> str | None:
    return value.isoformat() if value else None


def model_dump(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value
