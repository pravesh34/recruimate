"""Regression tests for the browse/add pool flow and resume viewing.

Covers the features changed when the job-search page moved to
"list first, add explicitly", the compatibility endpoint's pool-job
support, and the resume download fallback for seeded profiles.
"""
from __future__ import annotations

import uuid

import pytest

from tests.test_security import RESUME


def _email() -> str:
    return f"pool-{uuid.uuid4().hex[:10]}@example.com"


def _token(client) -> str:
    tokens = client.post(
        "/api/auth/register",
        json={"email": _email(), "password": "Str0ngPassw0rd", "display_name": "Pool"},
    ).json()
    return tokens["access_token"]


def _headers(client) -> dict:
    return {"Authorization": f"Bearer {_token(client)}"}


def _sample_listing(n: int = 0) -> dict:
    return {
        "title": f"Backend Engineer {n}",
        "company": "ACME",
        "location": "Remote",
        "url": f"https://remotive.com/jobs/test-{n}",
        "source": "remotive",
        "tags": ["python"],
        "description": "Build REST APIs with Python and FastAPI. Strong SQL skills required. "
        "1+ years of relevant experience through internships. B.Tech or BSc required.",
    }


def test_pool_search_persists_nothing(client):
    """Searching a board must not silently grow the caller's pool."""
    headers = _headers(client)
    from app.database.models import SessionLocal, JobPosting
    before = SessionLocal().query(JobPosting).count()
    response = client.post(
        "/api/jobs/pool/search",
        json={"source": "remotive", "query": "", "limit": 1},
        headers=headers,
    )
    # The live board may be unreachable in CI; only assert persistence when it answers.
    if response.status_code != 200:
        pytest.skip(f"board unavailable: {response.status_code}")
    after = SessionLocal().query(JobPosting).count()
    assert after == before
    for listing in response.json()["listings"]:
        assert {"title", "company", "url", "source", "tags", "snippet"} <= set(listing)


def test_import_single_adds_one_listing(client):
    headers = _headers(client)
    response = client.post(
        "/api/jobs/pool/import-single", json=_sample_listing(1), headers=headers
    )
    assert response.status_code == 200, response.text
    assert response.json()["added"] is True
    # Idempotent on URL: adding the same listing again does not duplicate it.
    again = client.post(
        "/api/jobs/pool/import-single", json=_sample_listing(1), headers=headers
    )
    assert again.json()["added"] is False
    pool = client.get("/api/jobs/pool", headers=headers).json()
    titles = [j["title"] for j in pool["jobs"]]
    assert titles.count(_sample_listing(1)["title"]) == 1


def test_import_single_requires_title_and_url(client):
    headers = _headers(client)
    bad = _sample_listing(2)
    bad.pop("url")
    assert client.post("/api/jobs/pool/import-single", json=bad, headers=headers).status_code == 422


def test_import_single_is_user_scoped(client):
    headers = _headers(client)
    client.post("/api/jobs/pool/import-single", json=_sample_listing(3), headers=headers)
    other = _headers(client)
    pool = client.get("/api/jobs/pool", headers=other).json()
    assert all(j["title"] != _sample_listing(3)["title"] for j in pool["jobs"])


def test_pool_job_can_be_used_for_compatibility(client):
    headers = _headers(client)
    upload = client.post(
        "/api/resume/upload",
        files={"file": ("resume.txt", RESUME.encode(), "text/plain")},
        headers=headers,
    )
    assert upload.status_code == 200, upload.text
    resume_id = upload.json()["id"]
    client.post("/api/jobs/pool/import-single", json=_sample_listing(4), headers=headers)
    pool = client.get("/api/jobs/pool", headers=headers).json()
    pool_id = pool["jobs"][0]["id"]
    response = client.post(
        "/api/compatibility/analyze",
        json={"resume_id": resume_id, "pool_job_id": pool_id},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    report = response.json()
    assert "overall_score" in report
    # The mirrored analysis belongs to the caller.
    listing = client.get("/api/jobs", headers=headers).json()
    assert any(job["id"] == report["job_id"] for job in listing)


def test_pool_job_of_another_user_is_404(client):
    owner = _headers(client)
    client.post("/api/jobs/pool/import-single", json=_sample_listing(5), headers=owner)
    pool = client.get("/api/jobs/pool", headers=owner).json()
    pool_id = pool["jobs"][0]["id"]
    other = _headers(client)
    response = client.post(
        "/api/compatibility/analyze",
        json={"resume_id": None, "pool_job_id": pool_id},
        headers=other,
    )
    assert response.status_code in (400, 404)


def test_resume_download_serves_canonical_pdf(client):
    """Every upload is rendered to a canonical PDF and served from it."""
    headers = _headers(client)
    upload = client.post(
        "/api/resume/upload",
        files={"file": ("resume.txt", RESUME.encode(), "text/plain")},
        headers=headers,
    )
    assert upload.status_code == 200, upload.text
    resume_id = upload.json()["id"]
    response = client.get(f"/api/resume/{resume_id}/download", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content[:5] == b"%PDF-"
    assert b"%%EOF" in response.content[-2048:]


def test_resume_download_falls_back_to_stored_text(client):
    """When neither the original file nor the PDF exists, the stored resume
    text is served instead of dead-ending with 404."""
    headers = _headers(client)
    upload = client.post(
        "/api/resume/upload",
        files={"file": ("resume.txt", RESUME.encode(), "text/plain")},
        headers=headers,
    )
    assert upload.status_code == 200, upload.text
    resume_id = upload.json()["id"]
    import pathlib

    from app.database.models import ResumeProfile, SessionLocal

    db = SessionLocal()
    try:
        row = db.get(ResumeProfile, resume_id)
        row.storage_path = str(pathlib.Path("/nonexistent/resume.txt"))  # simulate pruned storage
        row.pdf_path = ""
        db.commit()
    finally:
        db.close()
    response = client.get(f"/api/resume/{resume_id}/download", headers=headers)
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "Ravi Kumar" in response.text
