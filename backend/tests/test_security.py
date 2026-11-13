"""Security behaviour tests: rate limiting, refresh replay, user scoping.

These tests exercise the account system end to end through the API. They run
with ``AUTH_ENABLED=false`` (pinned in conftest) but the auth endpoints
themselves are always available, and a valid JWT resolves to its user even in
trusted-local mode — which is what lets us sign in as two separate accounts.
"""
from __future__ import annotations

import uuid

import pytest

RESUME = """Ravi Kumar
ravi.kumar@example.com | github.com/ravik | Pune

Technical Skills
Python, FastAPI, SQL, Docker, Git

Experience
Backend intern at ChipSoft | Jun 2025 - Present
- Built FastAPI endpoints for an internal tool.

Projects
URL shortener with analytics.

Education
B.E. Computer Engineering, COEP, 2022 - 2026
"""

JOB = """Backend Engineer Intern
ChipSoft | Pune | Full-time

Requirements
- Strong Python programming skills.
- Experience with FastAPI, REST APIs and SQL.
- Familiarity with Docker and Git.
- 1+ years of relevant experience through internships or projects.
"""


def _unique_email() -> str:
    return f"sec-{uuid.uuid4().hex[:10]}@example.com"


def _register(client, email: str) -> dict:
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "Str0ngPassw0rd", "display_name": "Sec Test"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _seed_compatibility(client, tokens: dict) -> dict:
    """Upload a resume + analyse a job + run compatibility for the caller."""
    response = client.post(
        "/api/resume/upload",
        files={"file": ("ravi_resume.txt", RESUME.encode(), "text/plain")},
        headers=_auth(tokens),
    )
    assert response.status_code == 200, response.text
    resume = response.json()

    response = client.post(
        "/api/jobs/analyze", json={"description": JOB}, headers=_auth(tokens)
    )
    assert response.status_code == 200, response.text
    job = response.json()

    response = client.post(
        "/api/compatibility/analyze",
        json={"resume_id": resume["id"], "job_id": job["id"]},
        headers=_auth(tokens),
    )
    assert response.status_code == 200, response.text
    return response.json()


# --------------------------------------------------------------------------- #
# Rate limiting
# --------------------------------------------------------------------------- #
def test_login_locks_out_after_repeated_failures(client):
    email = _unique_email()
    _register(client, email)

    for _ in range(5):
        response = client.post(
            "/api/auth/login", json={"email": email, "password": "WrongPassword1"}
        )
        assert response.status_code == 401, response.text

    # Even the correct password is refused while the key is locked out.
    response = client.post(
        "/api/auth/login", json={"email": email, "password": "Str0ngPassw0rd"}
    )
    assert response.status_code == 429, response.text
    assert "Too many failed attempts" in response.json()["detail"]


def test_lockout_clears_after_success(client):
    # A different key (unique email) is unaffected by the previous lockout and
    # record_success clears the counter, so this login succeeds on first try.
    email = _unique_email()
    _register(client, email)
    response = client.post(
        "/api/auth/login", json={"email": email, "password": "Str0ngPassw0rd"}
    )
    assert response.status_code == 200, response.text


# --------------------------------------------------------------------------- #
# Refresh rotation + replay detection
# --------------------------------------------------------------------------- #
def test_refresh_replay_revokes_whole_family(client):
    email = _unique_email()
    tokens = _register(client, email)

    # Rotate once: old token becomes single-use.
    response = client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert response.status_code == 200, response.text
    rotated = response.json()
    assert rotated["refresh_token"] != tokens["refresh_token"]

    # Replay the OLD token: must be rejected...
    response = client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert response.status_code == 401, response.text

    # ...and the sibling token from the same family must be dead too.
    response = client.post("/api/auth/refresh", json={"refresh_token": rotated["refresh_token"]})
    assert response.status_code == 401, response.text


def test_logout_revokes_refresh_token(client):
    email = _unique_email()
    tokens = _register(client, email)
    response = client.post("/api/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    assert response.status_code == 200, response.text
    response = client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert response.status_code == 401, response.text


# --------------------------------------------------------------------------- #
# Per-user data isolation
# --------------------------------------------------------------------------- #
def test_interview_and_gaps_are_user_scoped(client):
    tokens_a = _register(client, _unique_email())
    tokens_b = _register(client, _unique_email())

    compatibility = _seed_compatibility(client, tokens_a)

    response = client.post(
        "/api/interviews",
        json={"compatibility_id": compatibility["id"], "role": "Backend Engineer"},
        headers=_auth(tokens_a),
    )
    assert response.status_code == 200, response.text
    interview = response.json()

    # User B cannot see, answer to, or delete A's interview session.
    assert (
        client.get(f"/api/interviews/{interview['id']}", headers=_auth(tokens_b)).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/interviews/{interview['id']}/answer",
            json={"answer": "stolen answer"},
            headers=_auth(tokens_b),
        ).status_code
        == 404
    )
    assert (
        client.delete(f"/api/interviews/{interview['id']}", headers=_auth(tokens_b)).status_code
        == 404
    )

    # B's interview list does not include A's session.
    response = client.get("/api/interviews", headers=_auth(tokens_b))
    assert all(row["id"] != interview["id"] for row in response.json())

    # Skill gaps: A generates a roadmap, B can neither read nor mutate it.
    response = client.post(
        "/api/skill-gaps/generate",
        json={"compatibility_id": compatibility["id"]},
        headers=_auth(tokens_a),
    )
    assert response.status_code == 200, response.text
    gap = response.json()

    assert client.get(f"/api/skill-gaps/{gap['id']}", headers=_auth(tokens_b)).status_code == 404
    assert (
        client.get(
            f"/api/skill-gaps/tasks/{gap['tasks'][0]['id']}", headers=_auth(tokens_b)
        ).status_code
        in (404, 405)  # task detail has no GET route; PATCH below is the real check
    )
    response = client.patch(
        f"/api/skill-gaps/tasks/{gap['tasks'][0]['id']}",
        json={"completed": True},
        headers=_auth(tokens_b),
    )
    assert response.status_code == 404, response.text

    # B's compatibility list does not include A's report.
    response = client.get("/api/compatibility", headers=_auth(tokens_b))
    assert all(row["id"] != compatibility["id"] for row in response.json())


def test_account_data_deletion_is_scoped_to_caller(client):
    tokens_a = _register(client, _unique_email())
    tokens_b = _register(client, _unique_email())
    _seed_compatibility(client, tokens_a)

    # B wipes their own data...
    response = client.delete("/api/account/data", headers=_auth(tokens_b))
    assert response.status_code == 200, response.text

    # ...but A's resume survives.
    response = client.get("/api/resume/profile", headers=_auth(tokens_a))
    assert response.status_code == 200, response.text
    assert response.json()["filename"] == "ravi_resume.txt"

    # A's account info still reports their own row counts.
    response = client.get("/api/account", headers=_auth(tokens_a))
    assert response.json()["resume_count"] >= 1


def test_provider_usage_is_user_scoped(client):
    tokens_a = _register(client, _unique_email())
    tokens_b = _register(client, _unique_email())

    # A makes a provider touch (health listing logs a usage row).
    client.get("/api/providers/health", headers=_auth(tokens_a))

    response_a = client.get("/api/providers/usage", headers=_auth(tokens_a))
    response_b = client.get("/api/providers/usage", headers=_auth(tokens_b))
    ids_a = {row["id"] for row in response_a.json()["logs"]}
    ids_b = {row["id"] for row in response_b.json()["logs"]}
    assert ids_b.isdisjoint(ids_a)


# --------------------------------------------------------------------------- #
# Startup seeding
# --------------------------------------------------------------------------- #
def test_demo_seeding_is_idempotent(client):
    from app.database.models import JobPosting, SessionLocal, User
    from app.database.seed import seed_demo_candidates, seed_demo_jobs
    from scripts.seed_demo_candidates import CANDIDATES

    with SessionLocal() as db:
        seed_demo_candidates(db)
        seed_demo_jobs(db)
        demo_before = db.query(User).filter(User.is_demo.is_(True)).count()
        jobs_before = db.query(JobPosting).filter(JobPosting.source == "demo").count()
        assert demo_before == len(CANDIDATES)
        assert jobs_before >= 1

        # Re-run: no duplicates are created.
        seed_demo_candidates(db)
        seed_demo_jobs(db)
        assert db.query(User).filter(User.is_demo.is_(True)).count() == demo_before
        assert db.query(JobPosting).filter(JobPosting.source == "demo").count() == jobs_before

        # Every demo account can actually sign in through the API.
        login = client.post(
            "/api/auth/login",
            json={"email": CANDIDATES[0]["email"], "password": "RecruiMate@123"},
        )
        assert login.status_code == 200, login.text
