"""Target job pool tests: real-board import, per-candidate isolation, and the
plan-of-approach + mock-interview flows that read the pool directly.

The importer's HTTP layer is faked — no network in the test suite.
"""
from __future__ import annotations

import uuid

import pytest

RESUME = """Meera Nair
meera.nair@example.com | github.com/meeranair | Kochi

Technical Skills
Python, FastAPI, SQL, Docker, Git, REST APIs

Experience
Backend engineer at CloudKettle | 2024 - Present
- Built FastAPI services with PostgreSQL and Docker.

Projects
Internal tooling dashboards.

Education
B.Tech Computer Science, NIT Calicut, 2020 - 2024
"""


def _email() -> str:
    return f"pool-{uuid.uuid4().hex[:10]}@example.com"


def _auth(client, email: str) -> dict:
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "Str0ngPassw0rd", "display_name": "Pool"},
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _upload_resume(client, auth: dict) -> dict:
    response = client.post(
        "/api/resume/upload",
        files={"file": ("meera_resume.txt", RESUME.encode(), "text/plain")},
        headers=auth,
    )
    assert response.status_code == 200, response.text
    return response.json()


# --------------------------------------------------------------------------- #
# Fake board transport
# --------------------------------------------------------------------------- #
class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeTransport:
    """Remotive-style canned response regardless of the URL."""

    def __init__(self, payload):
        self.payload = payload
        self.calls: list[tuple[str, dict]] = []

    async def get(self, url, params=None):
        self.calls.append((url, params or {}))
        return FakeResponse(self.payload)


def _board_payload():
    return {
        "jobs": [
            {
                "title": "Backend Engineer (Python)",
                "company_name": "Flowline",
                "candidate_required_location": "Remote (Europe)",
                "url": "https://remotive.com/jobs/flowline-backend",
                "tags": ["Python", "FastAPI", "Docker", "PostgreSQL", "SQL"],
                "job_type": "full_time",
                "description": (
                    "<p>We are hiring a Backend Engineer to build APIs. Strong Python "
                    "and FastAPI skills required, SQL and Docker required. 3+ years of "
                    "backend experience preferred. Git required.</p>"
                ),
            },
            {
                "title": "Data Analyst",
                "company_name": "Chartly",
                "candidate_required_location": "Remote",
                "url": "https://remotive.com/jobs/chartly-analyst",
                "tags": ["SQL", "Excel", "Tableau"],
                "job_type": "contract",
                "description": (
                    "<p>Data Analyst role: SQL and Excel required, dashboards in "
                    "Tableau. 1+ years experience.</p>"
                ),
            },
        ]
    }


# --------------------------------------------------------------------------- #
# Import + isolation
# --------------------------------------------------------------------------- #
def test_pool_import_and_upsert(client, monkeypatch):
    import app.api.jobs as jobs_api
    from app.services import job_import

    transport = FakeTransport(_board_payload())
    monkeypatch.setattr(jobs_api, "fetch_postings", job_import.fetch_postings)

    async def fake_fetch(source, query="", limit=12, transport_override=None):
        return await job_import.fetch_postings(source, query, limit, transport)

    monkeypatch.setattr(jobs_api, "fetch_postings", fake_fetch)

    auth = _auth(client, _email())
    response = client.post(
        "/api/jobs/pool/import",
        json={"source": "remotive", "query": "", "limit": 10},
        headers=auth,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["imported"] == 2 and body["pool_size"] == 2

    pool = client.get("/api/jobs/pool", headers=auth).json()
    titles = {j["title"] for j in pool["jobs"]}
    assert titles == {"Backend Engineer (Python)", "Data Analyst"}

    backend = next(j for j in pool["jobs"] if j["title"].startswith("Backend"))
    assert "Python" in backend["skills"] and "FastAPI" in backend["skills"]
    assert backend["min_years_experience"] == 3.0

    # Re-import: same URLs update in place, no duplicates.
    response = client.post(
        "/api/jobs/pool/import",
        json={"source": "remotive", "query": "", "limit": 10},
        headers=auth,
    )
    assert response.json()["updated"] == 2 and response.json()["imported"] == 0
    assert client.get("/api/jobs/pool", headers=auth).json()["total"] == 2


def test_pool_is_per_candidate(client, monkeypatch):
    import app.api.jobs as jobs_api
    from app.services import job_import

    async def fake_fetch(source, query="", limit=12, transport=None):
        return await job_import.fetch_postings(source, query, limit, FakeTransport(_board_payload()))

    monkeypatch.setattr(jobs_api, "fetch_postings", fake_fetch)

    auth_a = _auth(client, _email())
    auth_b = _auth(client, _email())

    response = client.post("/api/jobs/pool/import", json={"source": "remotive", "query": ""}, headers=auth_a)
    assert response.status_code == 200, response.text
    assert response.json()["pool_size"] == 2

    # B's pool is empty: postings belong to the importer.
    assert client.get("/api/jobs/pool", headers=auth_b).json()["total"] == 0

    # B cannot delete or read A's pool row.
    a_row = client.get("/api/jobs/pool", headers=auth_a).json()["jobs"][0]
    assert client.delete(f"/api/jobs/pool/{a_row['id']}", headers=auth_b).status_code == 404

    # A's ranking only covers A's pool (shared demo postings excluded).
    _upload_resume(client, auth_a)
    matches = client.get("/api/jobs/match-resume", headers=auth_a).json()
    assert matches["total"] == 2
    assert all(m["in_pool"] for m in matches["matches"])

    # Shared (demo) postings only show up when explicitly requested.
    from app.database.models import JobPosting, SessionLocal
    from app.database.seed import seed_demo_jobs

    with SessionLocal() as db:
        seed_demo_jobs(db)
    matches_shared = client.get(
        "/api/jobs/match-resume", params={"include_shared": "true"}, headers=auth_a
    ).json()
    assert matches_shared["total"] == matches["total"] + 8
    assert any(not m["in_pool"] for m in matches_shared["matches"])


def test_pool_add_manual_and_delete(client):
    auth = _auth(client, _email())
    _upload_resume(client, auth)

    response = client.post(
        "/api/jobs/pool/add",
        json={
            "description": (
                "Platform Engineer at Stackgrid. Python and Docker required, "
                "Kubernetes preferred. 2+ years of experience running services."
            ),
            "title": "Platform Engineer",
            "company": "Stackgrid",
            "location": "Remote",
        },
        headers=auth,
    )
    assert response.status_code == 200, response.text
    job = response.json()["job"]
    assert job["title"] == "Platform Engineer"
    assert "Python" in job["skills"]

    assert client.delete(f"/api/jobs/pool/{job['id']}", headers=auth).status_code == 200
    assert client.get("/api/jobs/pool", headers=auth).json()["total"] == 0


def test_import_rejects_unknown_source(client):
    auth = _auth(client, _email())
    response = client.post(
        "/api/jobs/pool/import", json={"source": "indeed"}, headers=auth
    )
    assert response.status_code == 400, response.text


def test_import_surfaces_board_errors(client, monkeypatch):
    import app.api.jobs as jobs_api
    from app.services.job_import import ImportError as BoardImportError

    async def failing_fetch(source, query="", limit=12, transport=None):
        raise BoardImportError("Could not reach remotive: boom")

    monkeypatch.setattr(jobs_api, "fetch_postings", failing_fetch)
    auth = _auth(client, _email())
    response = client.post("/api/jobs/pool/import", json={"source": "remotive"}, headers=auth)
    assert response.status_code == 502, response.text


# --------------------------------------------------------------------------- #
# Plan of approach + mock interview from the pool
# --------------------------------------------------------------------------- #
def test_plan_of_approach_from_pool_job(client, monkeypatch):
    import app.api.jobs as jobs_api
    from app.services import job_import

    async def fake_fetch(source, query="", limit=12, transport=None):
        return await job_import.fetch_postings(source, query, limit, FakeTransport(_board_payload()))

    monkeypatch.setattr(jobs_api, "fetch_postings", fake_fetch)
    auth = _auth(client, _email())
    _upload_resume(client, auth)
    client.post("/api/jobs/pool/import", json={"source": "remotive"}, headers=auth)
    pool_job = client.get("/api/jobs/pool", headers=auth).json()["jobs"][0]

    response = client.post(
        "/api/skill-gaps/generate-for-job",
        json={"job_id": pool_job["id"]},
        headers=auth,
    )
    assert response.status_code == 200, response.text
    gap = response.json()
    assert gap["compatibility_id"] > 0
    assert 0 <= gap["compatibility_score"] <= 100
    assert gap["tasks"], "the roadmap must contain learning tasks"
    assert gap["job"]["company"] == pool_job["company"]

    # Another candidate cannot plan against someone else's pool job.
    auth_b = _auth(client, _email())
    assert (
        client.post(
            "/api/skill-gaps/generate-for-job", json={"job_id": pool_job["id"]}, headers=auth_b
        ).status_code
        == 404
    )


def test_mock_interview_from_pool_job(client, monkeypatch):
    import app.api.jobs as jobs_api
    from app.services import job_import

    async def fake_fetch(source, query="", limit=12, transport=None):
        return await job_import.fetch_postings(source, query, limit, FakeTransport(_board_payload()))

    monkeypatch.setattr(jobs_api, "fetch_postings", fake_fetch)
    auth = _auth(client, _email())
    _upload_resume(client, auth)
    client.post("/api/jobs/pool/import", json={"source": "remotive"}, headers=auth)
    pool_job = client.get("/api/jobs/pool", headers=auth).json()["jobs"][0]

    response = client.post(
        "/api/interviews/for-job",
        json={"job_id": pool_job["id"], "question_limit": 6},
        headers=auth,
    )
    assert response.status_code == 200, response.text
    session = response.json()
    assert session["status"] == "active"
    assert session["current_question"]["question"], "a first question must be asked"
    assert session["progress"]["total"] >= 6
    assert session["job"]["title"] == pool_job["title"]

    # Answer one question through the normal state machine.
    answer = client.post(
        f"/api/interviews/{session['id']}/answer",
        json={"answer": "I would design the API with FastAPI, use SQL for persistence and Docker for deploys."},
        headers=auth,
    )
    assert answer.status_code == 200, answer.text
    assert answer.json()["evaluation"]["overall"] >= 0

    # Other users cannot see or drive the session.
    auth_b = _auth(client, _email())
    assert client.get(f"/api/interviews/{session['id']}", headers=auth_b).status_code == 404
    assert (
        client.post(
            f"/api/interviews/{session['id']}/answer",
            json={"answer": "hi"},
            headers=auth_b,
        ).status_code
        == 404
    )
