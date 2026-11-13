"""API dependencies and shared serialisation helpers."""
from __future__ import annotations

import datetime as dt
from typing import Any

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from ..config import settings
from ..core.auth import decode_access_token
from ..database.models import User, get_db
from ..gateway import GatewayManager


def _bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the caller.

    Resolution order:
      1. A valid JWT access token -> that user.
      2. The legacy shared ``API_TOKEN`` -> the local candidate account.
      3. Nothing, when auth is disabled -> the local candidate account
         (trusted-local mode).

    Raises 401 when auth is enabled and no valid credential is present.
    """
    token = _bearer(authorization)

    if token:
        payload = decode_access_token(token)
        if payload:
            try:
                user_id = int(payload.get("sub", 0))
            except (TypeError, ValueError):
                user_id = 0
            user = db.get(User, user_id) if user_id else None
            if user and user.is_active:
                return user
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is inactive or no longer exists.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Not a JWT. Could still be the legacy shared API token.
        if settings.api_token and token == settings.api_token:
            return _local_user(db)

    if settings.api_token and not settings.auth_enabled:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if settings.auth_enabled:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in to continue.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return _local_user(db)


def _local_user(db: Session) -> User:
    """The single local candidate account used in trusted-local mode."""
    user = db.query(User).order_by(User.id).first()
    if user:
        return user
    user = User(email="candidate@local", display_name="Candidate")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


async def require_auth(authorization: str | None = Header(default=None)) -> None:
    """Legacy bearer-token gate kept for backwards compatibility.

    New code should depend on ``get_current_user`` instead, which also gives
    access to the resolved account.
    """
    if not settings.api_token:
        return
    expected = f"Bearer {settings.api_token}"
    if authorization != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_gateway(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> GatewayManager:
    """Gateway bound to the caller's provider configuration and usage logs."""
    return GatewayManager(db, user_id=user.id)


def iso(value: dt.datetime | None) -> str | None:
    return value.isoformat() if value else None


def model_dump(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value
