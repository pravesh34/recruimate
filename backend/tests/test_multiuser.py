"""Multi-user isolation regression tests.

Each test creates two independent accounts and proves that User A cannot
read, modify, delete or reference User B's private data. They exist as a
regression net for the scoping bugs fixed alongside this file:

* ``/api/jobs/analyze`` writing every user's analyses to the first account
* ``/api/compatibility/analyze`` accepting a foreign ``job_id`` and falling
  back to a globally-latest (cross-user) job analysis
* ``/api/account/data`` leaving pipeline entries / pool postings / sessions
  behind after deletion
"""
from __future__ import annotations

import uuid

import pytest

from tests.test_security import JOB, RESUME


def _email() -> str:
    return f"mu-{uuid.uuid4().hex[:10]}@example.com"


def _register(client, email: str | None = None) -> dict:
    email = email or _email()
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "Str0ngPassw0rd", "display_name": "MU"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _upload(client, headers) -> dict:
    response = client.post(
        "/api/resume/upload",
        files={"file": ("resume.txt", RESUME.encode(), "text/plain")},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _analyze_job(client, headers) -> dict:
    response = client.post("/api/jobs/analyze", json={"description": JOB}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_job_analyses_belong_to_the_calling_account(client):
    """A registered user's analysis must be attributed to her, not to the
    seeded local account (the ensure_default_user override bug)."""
    tokens_b = _register(client)
    job = _analyze_job(client, _auth(tokens_b))
    listing_b = client.get("/api/jobs", headers=_auth(tokens_b)).json()
    assert any(j["id"] == job["id"] for j in listing_b)


def test_user_a_cannot_score_against_user_b_job_id(client):
    """Cross-user job_id in /api/compatibility/analyze must 404."""
    tokens_a, tokens_b = _register(client), _register(client)
    job_b = _analyze_job(client, _auth(tokens_b))
    resume_a = _upload(client, _auth(tokens_a))
    response = client.post(
        "/api/compatibility/analyze",
        json={"resume_id": resume_a["id"], "job_id": job_b["id"]},
        headers=_auth(tokens_a),
    )
    assert response.status_code == 404, response.text


def test_latest_job_fallback_is_user_scoped(client):
    """With no job_id/description, the fallback must pick the caller's own
    latest analysis — never another user's."""
    tokens_a, tokens_b = _register(client), _register(client)
    _analyze_job(client, _auth(tokens_b))
    resume_a = _upload(client, _auth(tokens_a))
    response = client.post(
        "/api/compatibility/analyze",
        json={"resume_id": resume_a["id"], "job_description": ""},
        headers=_auth(tokens_a),
    )
    assert response.status_code == 400  # user A has no analyses of her own


def test_user_a_cannot_delete_user_b_job_analysis(client):
    tokens_a, tokens_b = _register(client), _register(client)
    job_b = _analyze_job(client, _auth(tokens_b))
    response = client.delete(f"/api/jobs/{job_b['id']}", headers=_auth(tokens_a))
    assert response.status_code == 404
    # user B still has it
    assert client.get(f"/api/jobs/{job_b['id']}", headers=_auth(tokens_b)).status_code == 200


def test_user_a_cannot_read_user_b_resume(client):
    tokens_a, tokens_b = _register(client), _register(client)
    resume_b = _upload(client, _auth(tokens_b))
    response = client.get(f"/api/resume/profile/{resume_b['id']}", headers=_auth(tokens_a))
    assert response.status_code == 404
    response = client.delete(f"/api/resume/{resume_b['id']}", headers=_auth(tokens_a))
    assert response.status_code == 404
    assert client.get("/api/resume/profile", headers=_auth(tokens_b)).status_code == 200


def test_user_a_cannot_read_user_b_interview_history(client):
    tokens_a, tokens_b = _register(client), _register(client)
    resume_b = _upload(client, _auth(tokens_b))
    job_b = _analyze_job(client, _auth(tokens_b))
    report = client.post(
        "/api/compatibility/analyze",
        json={"resume_id": resume_b["id"], "job_id": job_b["id"]},
        headers=_auth(tokens_b),
    ).json()
    session = client.post(
        "/api/interviews",
        json={"compatibility_id": report["id"], "kind": "mock"},
        headers=_auth(tokens_b),
    ).json()
    response = client.get(f"/api/interviews/{session['id']}", headers=_auth(tokens_a))
    assert response.status_code == 404
    response = client.delete(f"/api/interviews/{session['id']}", headers=_auth(tokens_a))
    assert response.status_code == 404
    # user B can still see it
    listing_b = client.get("/api/interviews", headers=_auth(tokens_b)).json()
    assert any(i["id"] == session["id"] for i in (listing_b if isinstance(listing_b, list) else listing_b.get("sessions", [])))


def test_user_a_cannot_modify_user_b_learning_tasks(client):
    tokens_a, tokens_b = _register(client), _register(client)
    resume_b = _upload(client, _auth(tokens_b))
    job_b = _analyze_job(client, _auth(tokens_b))
    report = client.post(
        "/api/compatibility/analyze",
        json={"resume_id": resume_b["id"], "job_id": job_b["id"]},
        headers=_auth(tokens_b),
    ).json()
    gap = client.post(
        "/api/skill-gaps/generate",
        json={"compatibility_id": report["id"]},
        headers=_auth(tokens_b),
    ).json()
    tasks = client.get(f"/api/skill-gaps/{gap['id']}", headers=_auth(tokens_b)).json().get(
        "tasks", []
    )
    if not tasks:
        pytest.skip("no tasks generated for this resume/job pair")
    response = client.patch(
        f"/api/skill-gaps/tasks/{tasks[0]['id']}",
        json={"completed": True},
        headers=_auth(tokens_a),
    )
    assert response.status_code == 404


def test_user_a_cannot_use_user_b_pipeline_or_pool(client):
    tokens_a, tokens_b = _register(client), _register(client)
    posting_b = client.post(
        "/api/jobs/pool/import-single",
        json={"url": "https://example.com/job"},
        headers=_auth(tokens_b),
    )
    if posting_b.status_code != 200:
        pytest.skip("pool import-single unavailable in this environment")
    response = client.post(
        "/api/pipeline", json={"job_id": posting_b.json()["id"]}, headers=_auth(tokens_a)
    )
    assert response.status_code in (404, 400)


def test_account_deletion_removes_every_private_row(client):
    """Deletion must also clear pipeline entries, the user's pool postings
    and every refresh session."""
    tokens = _register(client)
    headers = _auth(tokens)
    resume = _upload(client, headers)
    job = _analyze_job(client, headers)
    client.post(
        "/api/compatibility/analyze",
        json={"resume_id": resume["id"], "job_id": job["id"]},
        headers=headers,
    )
    client.post("/api/pipeline", json={"title": "Track me", "company": "ACME"}, headers=headers)

    assert client.delete("/api/account/data", headers=headers).status_code == 200

    from app.database.models import SessionLocal
    from app.database.models import (
        AuthSession,
        CompatibilityReport,
        JobAnalysis,
        JobPosting,
        LearningTask,
        PipelineEntry,
        ResumeProfile,
        SkillGapReport,
        UsageLog,
    )

    user_id = tokens["user"]["id"]
    models = [ResumeProfile, JobAnalysis, CompatibilityReport, SkillGapReport,
              PipelineEntry, JobPosting, AuthSession, UsageLog]
    db = SessionLocal()
    try:
        for model in models:
            assert db.query(model).filter(model.user_id == user_id).count() == 0, model.__name__
    finally:
        db.close()

    # Old refresh tokens no longer resolve to anything usable.
    refresh = client.post(
        "/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refresh.status_code == 401


def test_uploaded_file_signature_is_validated(client):
    """A text payload renamed to .pdf must be rejected before it is parsed."""
    tokens = _register(client)
    response = client.post(
        "/api/resume/upload",
        files={"file": ("fake.pdf", b"#!/bin/bash\nrm -rf / \n" * 5, "application/pdf")},
        headers=_auth(tokens),
    )
    assert response.status_code == 400
    assert "not a valid PDF" in response.json()["detail"]


def test_security_headers_are_set(client):
    response = client.get("/api/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "same-origin"


def test_provider_configuration_is_per_user(client):
    """User B's stored API key must not be visible to user A."""
    tokens_a, tokens_b = _register(client), _register(client)
    response_b = client.put(
        "/api/providers/configuration",
        json={"provider": "openrouter", "api_key": "sk-or-test-secret-value"},
        headers=_auth(tokens_b),
    )
    assert response_b.status_code == 200, response_b.text
    listing_a = client.get("/api/providers", headers=_auth(tokens_a)).json()
    flat = str(listing_a)
    assert "sk-or-test-secret-value" not in flat
