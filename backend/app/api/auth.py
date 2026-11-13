"""Authentication endpoints: register, login, refresh, logout, session list."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from ..config import settings
from ..core.auth import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    is_session_active,
    password_strength_errors,
    refresh_token_expiry,
    verify_password,
)
from ..database.models import AuthSession, User, get_db
from .deps import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #
class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)
    display_name: str = Field(default="", max_length=120)


class LoginRequest(BaseModel):
    email: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=1, max_length=128)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def user_to_dict(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "is_active": user.is_active,
        "is_demo": user.is_demo,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
    }


def _issue_tokens(
    db: Session,
    user: User,
    request: Request | None = None,
) -> dict:
    """Create an access token plus a persisted refresh session."""
    access_token, expires_in = create_access_token(user.id, user.role, user.email)

    refresh_token = generate_refresh_token()
    session = AuthSession(
        user_id=user.id,
        token_hash=hash_refresh_token(refresh_token),
        expires_at=refresh_token_expiry(),
        user_agent=(request.headers.get("user-agent", "")[:512] if request else ""),
        ip_address=(request.client.host[:64] if request and request.client else ""),
    )
    db.add(session)
    db.commit()

    user.last_login_at = dt.datetime.now(dt.timezone.utc)
    db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "user": user_to_dict(user),
    }


def _find_user(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email.strip().lower()).first()


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #
@router.get("/status")
def auth_status(db: Session = Depends(get_db)):
    """Report whether the account system is switched on."""
    return {
        "auth_enabled": bool(settings.auth_enabled),
        "demo_accounts": db.query(User).filter(User.is_demo.is_(True)).count(),
    }


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    """Create a new candidate account and sign it in."""
    email = payload.email.strip().lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(400, "Enter a valid email address.")

    errors = password_strength_errors(payload.password)
    if errors:
        raise HTTPException(400, " ".join(errors))

    if _find_user(db, email):
        raise HTTPException(409, "An account with that email already exists.")

    user = User(
        email=email,
        display_name=(payload.display_name.strip() or email.split("@")[0])[:120],
        password_hash=hash_password(payload.password),
        role="candidate",
        is_local=False,
        is_active=True,
        is_demo=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _issue_tokens(db, user, request)


@router.post("/login")
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """Exchange credentials for an access token and refresh session."""
    user = _find_user(db, payload.email)
    # Same message for unknown user and wrong password: no account enumeration.
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(403, "This account has been deactivated.")
    return _issue_tokens(db, user, request)


@router.post("/refresh")
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    """Exchange a refresh token for a new access token."""
    token_hash = hash_refresh_token(payload.refresh_token)
    session = db.query(AuthSession).filter(AuthSession.token_hash == token_hash).first()
    if not is_session_active(session):
        raise HTTPException(401, "Your session has expired. Please sign in again.")

    user = db.get(User, session.user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "Account is inactive or no longer exists.")

    access_token, expires_in = create_access_token(user.id, user.role, user.email)

    # Rotate the refresh token: the old one is single-use.
    session.revoked_at = dt.datetime.now(dt.timezone.utc)
    new_refresh = generate_refresh_token()
    db.add(
        AuthSession(
            user_id=user.id,
            token_hash=hash_refresh_token(new_refresh),
            expires_at=refresh_token_expiry(),
            user_agent=session.user_agent,
            ip_address=session.ip_address,
        )
    )
    db.commit()

    return {
        "access_token": access_token,
        "refresh_token": new_refresh,
        "token_type": "bearer",
        "expires_in": expires_in,
        "user": user_to_dict(user),
    }


@router.post("/logout")
def logout(payload: RefreshRequest, db: Session = Depends(get_db)):
    """Revoke a refresh session. Access tokens expire on their own."""
    token_hash = hash_refresh_token(payload.refresh_token)
    session = db.query(AuthSession).filter(AuthSession.token_hash == token_hash).first()
    if session and session.revoked_at is None:
        session.revoked_at = dt.datetime.now(dt.timezone.utc)
        db.commit()
    return {"revoked": True}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    """Return the signed-in account."""
    return user_to_dict(user)


@router.get("/sessions")
def list_sessions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List the caller's active and revoked sign-in sessions."""
    rows = (
        db.query(AuthSession)
        .filter(AuthSession.user_id == user.id)
        .order_by(AuthSession.created_at.desc())
        .all()
    )
    now = dt.datetime.now(dt.timezone.utc)
    return [
        {
            "id": s.id,
            "user_agent": s.user_agent,
            "ip_address": s.ip_address,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "expires_at": s.expires_at.isoformat() if s.expires_at else None,
            "active": is_session_active(s),
        }
        for s in rows
    ]


@router.post("/sessions/{session_id}/revoke")
def revoke_session(
    session_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke one of the caller's sessions."""
    session = db.get(AuthSession, session_id)
    if not session or session.user_id != user.id:
        raise HTTPException(404, "Session not found.")
    if session.revoked_at is None:
        session.revoked_at = dt.datetime.now(dt.timezone.utc)
        db.commit()
    return {"revoked": True, "id": session_id}


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change the signed-in account's password and revoke other sessions."""
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(400, "Your current password is incorrect.")

    errors = password_strength_errors(payload.new_password)
    if errors:
        raise HTTPException(400, " ".join(errors))

    user.password_hash = hash_password(payload.new_password)
    db.commit()

    # Revoke every existing session so other devices must sign in again.
    now = dt.datetime.now(dt.timezone.utc)
    for session in db.query(AuthSession).filter(
        AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)
    ):
        session.revoked_at = now
    db.commit()
    return {"changed": True}
