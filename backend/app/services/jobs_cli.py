"""Safe integration with the external ``jobs-cli`` binary.

`jobs-cli` (github.com/thedavidweng/jobs-cli) is an agent-native CLI that
searches Indeed, LinkedIn and a few public boards and prints a stable JSON
envelope when called with ``--json``.

This module is a deliberately small, defensive wrapper:

* Only an **allow-list of read-only commands** may be executed. ``apply``
  commands are rejected outright, so RecruiMate can never submit an
  application or send a message on a candidate's behalf.
* The binary is executed **without a shell** (``create_subprocess_exec``) so
  nothing in a query or location can be interpreted as shell syntax.
* Every argument value is passed as ``--flag=value`` so a value that starts
  with ``-`` cannot be read as another flag.
* The CLI's own session/credential store (``~/.jobs-cli``) is never read,
  copied or returned by this module — the CLI keeps those secrets.
* Timeouts, a per-user rate limit and a short-lived cache keep a slow or
  misbehaving CLI from stalling the API.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import time
from dataclasses import dataclass, field
from typing import Any

from ..config import settings

# Commands RecruiMate is allowed to run. Anything else (apply/auth) is refused.
ALLOWED_COMMANDS: tuple[str, ...] = ("search", "show", "sources", "doctor")

# Sources the CLI understands (kept in sync with the CLI's own source list).
CLI_SOURCES: tuple[str, ...] = ("indeed", "linkedin", "yzi", "civicinfo", "translink")


class JobsCliError(RuntimeError):
    """Raised when the CLI is missing, misbehaving or returns an error."""

    def __init__(self, message: str, code: str = "JOBS_CLI_ERROR", retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


@dataclass
class CliResult:
    ok: bool
    data: Any = None
    meta: dict[str, Any] = field(default_factory=dict)
    error: dict[str, Any] = field(default_factory=dict)
    duration_ms: int = 0


def binary_path() -> str | None:
    """Absolute path of the CLI binary, or ``None`` when it is not installed."""
    configured = (settings.jobs_cli_bin or "").strip()
    if configured:
        path = shutil.which(configured) or (configured if os.path.isfile(configured) else None)
        return path
    return shutil.which("jobs-cli")


def is_available() -> bool:
    return bool(settings.jobs_cli_enabled and binary_path())


def unavailable_reason() -> str:
    if not settings.jobs_cli_enabled:
        return "The Jobs CLI integration is disabled (set JOBS_CLI_ENABLED=true to turn it on)."
    if not binary_path():
        return (
            "The 'jobs-cli' binary was not found on PATH. Install it with "
            "`curl -fsSL https://raw.githubusercontent.com/thedavidweng/jobs-cli/main/install.sh | sh` "
            "or set JOBS_CLI_BIN to its absolute path."
        )
    return ""


# --------------------------------------------------------------------------- #
# Rate limiting (per user, in-process)
# --------------------------------------------------------------------------- #
_rate_state: dict[str, list[float]] = {}


def _rate_key(user_id: int) -> str:
    return f"cli:{user_id}"


def check_rate_limit(user_id: int) -> tuple[bool, int]:
    """Return ``(allowed, retry_after_seconds)`` for CLI calls of one user."""
    limit = max(1, settings.jobs_cli_rate_limit_per_minute)
    window = 60.0
    now = time.monotonic()
    key = _rate_key(user_id)
    calls = [t for t in _rate_state.get(key, []) if now - t < window]
    if len(calls) >= limit:
        _rate_state[key] = calls
        return False, int(window - (now - calls[0])) + 1
    calls.append(now)
    _rate_state[key] = calls
    return True, 0


# --------------------------------------------------------------------------- #
# Cache
# --------------------------------------------------------------------------- #
_cache: dict[str, tuple[float, Any]] = {}


def cache_get(key: str) -> Any | None:
    """Return a cached CLI response, or ``None`` when missing/expired."""
    ttl = max(0, settings.jobs_cli_cache_ttl)
    if not ttl:
        return None
    hit = _cache.get(key)
    if not hit:
        return None
    created, value = hit
    if time.monotonic() - created > ttl:
        _cache.pop(key, None)
        return None
    return value


def cache_set(key: str, value: Any) -> None:
    """Store a CLI response in the short-lived cache."""
    _cache[key] = (time.monotonic(), value)


def clear_cache() -> None:
    _cache.clear()


# --------------------------------------------------------------------------- #
# Execution
# --------------------------------------------------------------------------- #
_SECRET_HINTS = ("cookie", "password", "passwd", "token", "authorization", "session")


def _redact(text: str) -> str:
    """Strip anything that looks like a credential out of CLI output."""
    out = text or ""
    lowered = out.lower()
    if any(hint in lowered for hint in _SECRET_HINTS):
        return "The CLI output was redacted because it may contain credentials."
    return out[:2000]


async def run_cli(
    args: list[str],
    *,
    timeout: float | None = None,
    user_id: int | None = None,
) -> CliResult:
    """Execute an allow-listed ``jobs-cli`` command and return the parsed envelope."""
    if not args:
        raise JobsCliError("No command given.", code="INVALID_ARGUMENTS")
    command = args[0]
    if command not in ALLOWED_COMMANDS:
        raise JobsCliError(
            f"Command '{command}' is not permitted. RecruiMate only runs read-only "
            f"commands ({', '.join(ALLOWED_COMMANDS)}).",
            code="READ_ONLY_VIOLATION",
        )
    if not settings.jobs_cli_enabled:
        raise JobsCliError(unavailable_reason(), code="JOBS_CLI_DISABLED")
    binary = binary_path()
    if not binary:
        raise JobsCliError(unavailable_reason(), code="JOBS_CLI_MISSING")
    if user_id is not None:
        allowed, retry_after = check_rate_limit(user_id)
        if not allowed:
            raise JobsCliError(
                f"Too many Jobs CLI requests. Try again in {retry_after} seconds.",
                code="RATE_LIMITED",
                retryable=True,
            )

    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "JOBS_CONFIG_DIR": settings.jobs_cli_config_dir,
    }
    if settings.jobs_cli_country:
        env["JOBS_COUNTRY"] = settings.jobs_cli_country
    # Anything else the user configured for the CLI (JOBS_PROFILE, ...) passes
    # through untouched, but is never logged or returned.
    for key, value in os.environ.items():
        if key.startswith("JOBS_") and key not in env:
            env[key] = value

    full_args = [binary, *args]
    if "--json" not in args:
        full_args.append("--json")

    started = time.perf_counter()
    try:
        proc = await asyncio.create_subprocess_exec(
            *full_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
    except (OSError, ValueError) as exc:
        raise JobsCliError(f"Could not start the Jobs CLI: {exc}", code="JOBS_CLI_MISSING") from exc

    limit = timeout if timeout is not None else settings.jobs_cli_timeout
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=limit)
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        await asyncio.wait_for(proc.wait(), timeout=5)
        raise JobsCliError(
            f"The Jobs CLI did not respond within {int(limit)} seconds.",
            code="NETWORK_TIMEOUT",
            retryable=True,
        ) from None

    duration_ms = int((time.perf_counter() - started) * 1000)
    text = stdout.decode("utf-8", errors="replace").strip()
    if not text:
        message = _redact(stderr.decode("utf-8", errors="replace").strip())
        raise JobsCliError(
            message or "The Jobs CLI returned no output.",
            code="INTERNAL_ERROR",
            retryable=proc.returncode != 0,
        )

    import json

    try:
        payload = json.loads(text)
    except ValueError as exc:
        raise JobsCliError(
            "The Jobs CLI returned output that is not valid JSON.", code="API_SCHEMA_CHANGED"
        ) from exc

    if not isinstance(payload, dict):
        raise JobsCliError("Unexpected Jobs CLI response shape.", code="API_SCHEMA_CHANGED")

    if payload.get("ok") is False:
        error = payload.get("error") or {}
        raise JobsCliError(
            error.get("message") or "The Jobs CLI reported an error.",
            code=error.get("code") or "INTERNAL_ERROR",
            retryable=bool(error.get("retryable")),
        )

    return CliResult(
        ok=True,
        data=payload.get("data"),
        meta=payload.get("meta") or {},
        duration_ms=duration_ms,
    )


# --------------------------------------------------------------------------- #
# Typed helpers
# --------------------------------------------------------------------------- #
async def search(
    *,
    query: str = "",
    location: str = "",
    sources: list[str] | None = None,
    remote: bool = False,
    limit: int = 25,
    offset: int = 0,
    country: str = "",
    user_id: int | None = None,
) -> CliResult:
    """Run ``jobs-cli search`` (read-only)."""
    args: list[str] = ["search"]
    chosen = [s for s in (sources or []) if s in CLI_SOURCES]
    for source in chosen:
        args.append(f"--source={source}")
    if query.strip():
        args.append(f"--query={query.strip()[:200]}")
    if location.strip():
        args.append(f"--location={location.strip()[:200]}")
    if remote:
        args.append("--remote")
    args.append(f"--limit={max(1, min(int(limit), 100))}")
    if offset:
        args.append(f"--offset={max(0, int(offset))}")
    market = (country or settings.jobs_cli_country or "").strip()
    if market:
        args.append(f"--country={market[:8].upper()}")
    return await run_cli(args, user_id=user_id)


async def show(job_id: str, *, user_id: int | None = None) -> CliResult:
    """Run ``jobs-cli show <id> --resolve`` (read-only)."""
    safe_id = (job_id or "").strip()
    if not safe_id or len(safe_id) > 200 or not all(c.isalnum() or c in ":_.-" for c in safe_id):
        raise JobsCliError("Invalid job reference.", code="INVALID_ARGUMENTS")
    return await run_cli(["show", safe_id, "--resolve"], user_id=user_id)


async def sources_status(*, user_id: int | None = None) -> CliResult:
    return await run_cli(["sources", "status"], user_id=user_id)


async def doctor(*, user_id: int | None = None) -> CliResult:
    return await run_cli(["doctor"], user_id=user_id)
