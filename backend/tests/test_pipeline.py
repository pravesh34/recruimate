"""Application-pipeline tests: tracking pool jobs, status moves, isolation."""
from __future__ import annotations

import uuid


def _email() -> str:
    return f"pipe-{uuid.uuid4().hex[:10]}@example.com"


def _auth(client, email: str) -> dict:
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "Str0ngPassw0rd", "display_name": "Pipe"},
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _pool_job(client, auth: dict) -> dict:
    """Create a pool posting manually (no network needed)."""
    response = client.post(
        "/api/jobs/pool/add",
        json={
            "description": (
                "Backend Engineer at Streamline. Python and FastAPI required, "
                "SQL and Docker required. 2+ years of experience."
            ),
            "title": "Backend Engineer",
            "company": "Streamline",
            "location": "Remote",
        },
        headers=auth,
    )
    assert response.status_code == 200, response.text
    return response.json()["job"]


def test_track_from_pool_and_list(client):
    auth = _auth(client, _email())
    job = _pool_job(client, auth)

    response = client.post("/api/pipeline", json={"job_id": job["id"]}, headers=auth)
    assert response.status_code == 200, response.text
    entry = response.json()
    assert entry["title"] == "Backend Engineer"
    assert entry["company"] == "Streamline"
    assert entry["status"] == "new"
    assert entry["job_posting_id"] == job["id"]

    listing = client.get("/api/pipeline", headers=auth).json()
    assert listing["summary"]["new"] == 1
    assert listing["entries"][0]["title"] == "Backend Engineer"


def test_status_moves_and_validation(client):
    auth = _auth(client, _email())
    job = _pool_job(client, auth)
    entry = client.post("/api/pipeline", json={"job_id": job["id"]}, headers=auth).json()

    moved = client.patch(
        f"/api/pipeline/{entry['id']}",
        json={"status": "applied", "notes": "Applied via careers page", "next_action_at": "2026-11-20"},
        headers=auth,
    )
    assert moved.status_code == 200, moved.text
    body = moved.json()
    assert body["status"] == "applied"
    assert body["notes"] == "Applied via careers page"
    assert body["next_action_at"].startswith("2026-11-20")

    listing = client.get("/api/pipeline", headers=auth).json()
    assert listing["summary"]["applied"] == 1
    assert listing["summary"]["new"] == 0

    bad = client.patch(f"/api/pipeline/{entry['id']}", json={"status": "ghosted"}, headers=auth)
    assert bad.status_code == 400, bad.text

    clear = client.patch(f"/api/pipeline/{entry['id']}", json={"next_action_at": ""}, headers=auth)
    assert clear.status_code == 200 and clear.json()["next_action_at"] is None


def test_manual_entry_requires_title(client):
    auth = _auth(client, _email())
    response = client.post("/api/pipeline", json={"company": "NoTitle"}, headers=auth)
    assert response.status_code == 400, response.text

    manual = client.post(
        "/api/pipeline",
        json={"title": "Growth Marketer", "company": "Acme", "url": "https://acme.example/jobs/1"},
        headers=auth,
    )
    assert manual.status_code == 200, manual.text
    entry = manual.json()
    assert entry["source"] == "manual" and entry["job_posting_id"] is None


def test_pipeline_is_per_candidate(client):
    auth_a = _auth(client, _email())
    auth_b = _auth(client, _email())
    job = _pool_job(client, auth_a)

    entry = client.post("/api/pipeline", json={"job_id": job["id"]}, headers=auth_a).json()

    assert client.get("/api/pipeline", headers=auth_b).json()["entries"] == []
    assert (
        client.patch(f"/api/pipeline/{entry['id']}", json={"status": "offer"}, headers=auth_b).status_code
        == 404
    )
    assert client.delete(f"/api/pipeline/{entry['id']}", headers=auth_b).status_code == 404


def test_delete_entry(client):
    auth = _auth(client, _email())
    job = _pool_job(client, auth)
    entry = client.post("/api/pipeline", json={"job_id": job["id"]}, headers=auth).json()
    assert client.delete(f"/api/pipeline/{entry['id']}", headers=auth).status_code == 200
    assert client.get("/api/pipeline", headers=auth).json()["entries"] == []
