"""Small in-memory brute-force protection for the auth endpoints.

Sliding-window failure counting keyed by ``(client ip, account email)``.
After ``max_failures`` failed attempts inside ``window_seconds`` the key is
locked out for ``lockout_seconds``. State lives in the process only: it is
cheap, needs no infra and resets on restart — appropriate for a single-node
local app, and still raises the bar well above "unlimited guesses".
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

MAX_FAILURES = 5
WINDOW_SECONDS = 15 * 60  # count failures inside a 15 minute window
LOCKOUT_SECONDS = 15 * 60  # lock the key out for 15 minutes after that

_lock = threading.Lock()
_failures: dict[str, deque[float]] = defaultdict(deque)
_locked_until: dict[str, float] = {}


def key_for(ip: str, email: str) -> str:
    return f"{ip[:64]}|{email.strip().lower()[:255]}"


def _now() -> float:
    return time.monotonic()


def is_locked(key: str) -> tuple[bool, int]:
    """``(locked, retry_after_seconds)`` for the given key."""
    with _lock:
        deadline = _locked_until.get(key, 0.0)
        now = _now()
        if deadline <= now:
            _locked_until.pop(key, None)
            return False, 0
        return True, int(deadline - now) + 1


def record_failure(key: str) -> None:
    """Note one failed attempt; trips the lockout at MAX_FAILURES."""
    with _lock:
        now = _now()
        bucket = _failures[key]
        bucket.append(now)
        while bucket and now - bucket[0] > WINDOW_SECONDS:
            bucket.popleft()
        if len(bucket) >= MAX_FAILURES:
            _locked_until[key] = now + LOCKOUT_SECONDS
            _failures.pop(key, None)


def record_success(key: str) -> None:
    """Clear the failure history after a successful login."""
    with _lock:
        _failures.pop(key, None)
        _locked_until.pop(key, None)
