"""Authentication primitives: password hashing, JWT issuing and session tokens.

Design notes
------------
* Passwords are hashed with bcrypt through passlib. The plaintext never leaves
  the request handler.
* Access tokens are short-lived signed JWTs (stateless). They carry the user id
  and role so authorisation needs no database round-trip.
* Refresh tokens are opaque random strings. Only their SHA-256 digest is
  stored, so a database leak cannot be replayed as a login.
* ``AUTH_ENABLED=false`` keeps the original trusted-local behaviour: every
  request is treated as the single local candidate.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import secrets
from typing import Any

import bcrypt
from jose import JWTError, jwt

from ..config import settings


def _prepare(password: str) -> bytes:
    """Return the bytes to hand to bcrypt.

    bcrypt ignores bytes past 72, so long passwords are pre-hashed with
    SHA-256 and the digest is hashed instead. This preserves the full entropy
    of a long passphrase without triggering bcrypt's truncation warning.
    """
    raw = (password or "").encode("utf-8")
    if len(raw) > 72:
        return hashlib.sha256(raw).hexdigest().encode("ascii")
    return raw


# --------------------------------------------------------------------------- #
# Passwords
# --------------------------------------------------------------------------- #
def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt. Returns a PHC-style string."""
    return bcrypt.hashpw(_prepare(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Check a plaintext password against a stored hash. Never raises."""
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(_prepare(password), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def password_strength_errors(password: str) -> list[str]:
    """Return a list of human-readable password policy violations."""
    errors: list[str] = []
    if len(password or "") < 8:
        errors.append("Password must be at least 8 characters long.")
    if not any(c.islower() for c in password or ""):
        errors.append("Password must contain a lowercase letter.")
    if not any(c.isupper() for c in password or ""):
        errors.append("Password must contain an uppercase letter.")
    if not any(c.isdigit() for c in password or ""):
        errors.append("Password must contain a digit.")
    return errors


# --------------------------------------------------------------------------- #
# Access tokens (JWT)
# --------------------------------------------------------------------------- #
def create_access_token(user_id: int, role: str, email: str) -> tuple[str, int]:
    """Create a signed access token. Returns ``(token, expires_in_seconds)``."""
    expires_in = settings.access_token_minutes * 60
    now = dt.datetime.now(dt.timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "email": email,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + dt.timedelta(seconds=expires_in)).timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires_in


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decode and verify a JWT. Returns ``None`` when invalid or expired."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
    if payload.get("type") != "access":
        return None
    return payload


# --------------------------------------------------------------------------- #
# Refresh tokens (opaque, stored hashed)
# --------------------------------------------------------------------------- #
def generate_refresh_token() -> str:
    """Create an opaque refresh token (URL-safe, 256 bits of entropy)."""
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    """Digest a refresh token for storage.

    HMAC-SHA256 keyed with ``JWT_SECRET``. SHA-256 alone (the previous scheme)
    is fine against brute force for a high-entropy token, but the keyed hash
    means a database leak alone cannot verify stolen tokens without the app
    secret as well.
    """
    return hmac.new(
        settings.jwt_secret.encode("utf-8"), token.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def legacy_hash_refresh_token(token: str) -> str:
    """Pre-HMAC scheme (plain SHA-256). Kept only to verify sessions created
    before the upgrade; those rows re-hash on their next successful refresh."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def refresh_token_expiry() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=settings.refresh_token_days)


def is_session_active(session) -> bool:
    """True when a session row can still be exchanged for a new access token."""
    if session is None:
        return False
    if session.revoked_at is not None:
        return False
    expires = session.expires_at
    if expires is None:
        return False
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=dt.timezone.utc)
    return expires > dt.datetime.now(dt.timezone.utc)
