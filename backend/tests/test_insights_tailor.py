"""Pool insights (skill unlocks + combined roadmap) and resume tailoring."""
from __future__ import annotations

import uuid


def _email() -> str:
    return f"insight-{uuid.uuid4().hex[:10]}@example.com"


def _auth(client, email: str) -> dict:
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "Str0ngPassw0rd", "display_name": "Insight"},
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _setup(client, auth: dict) -> None:
    resume = client.post(
        "/api/resume/upload",
        files={
            "file": (
                "dev_resume.txt",
                (
                    "Meera Nair\nmeera@example.com\n\nTechnical Skills\n"
                    "Python, FastAPI, SQL, Docker, Git, REST APIs\n\nExperience\n"
                    "Backend engineer at CloudKettle | 2024 - Present\n"
                    "- Built FastAPI services with PostgreSQL and Docker.\n"
                    "- Automated deploys with GitLab CI.\n\nProjects\n"
                    "Internal dashboards with React.\n\nEducation\n"
                    "B.Tech Computer Science, NIT Calicut, 2020 - 2024\n"
                ).encode(),
                "text/plain",
            )
        },
        headers=auth,
    )
    assert resume.status_code == 200, resume.text

    for title, company, description in (
        (
            "Backend Engineer",
            "Streamline",
            "Python and FastAPI required, SQL and Docker required, Git required. 2+ years.",
        ),
        (
            "Platform Engineer",
            "Stackgrid",
            "Kubernetes and AWS required, Python required, Terraform required. 3+ years.",
        ),
        (
            "Data Engineer",
            "Floodlight",
            "SQL and Python required, Airflow required, Kafka required. 2+ years.",
        ),
    ):
        response = client.post(
            "/api/jobs/pool/add",
            json={"description": f"{title} at {company}. {description}", "title": title, "company": company},
            headers=auth,
        )
        assert response.status_code == 200, response.text


def test_insights_rank_skills_by_unlocks(client):
    auth = _auth(client, _email())
    _setup(client, auth)

    response = client.get("/api/jobs/pool/insights", headers=auth)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["jobs_scored"] == 3
    assert 0 <= body["average_score"] <= 100
    assert body["best_job"]["job_id"] > 0

    unlocks = body["skill_unlocks"]
    assert unlocks, "there must be at least one unlock skill"
    # Unlocks must be non-increasing (ranked by how many jobs they block).
    counts = [u["unlocks"] for u in unlocks]
    assert counts == sorted(counts, reverse=True)
    # Python is required by all three postings and absent from the resume's
    # canonical skill list, so it should surface at the top.
    assert unlocks[0]["skill"].lower() in {"python", "sql", "kubernetes", "airflow", "kafka", "aws", "terraform"}


def test_insights_empty_pool(client):
    auth = _auth(client, _email())
    response = client.post(
        "/api/resume/upload",
        files={
            "file": (
                "r.txt",
                (
                    "Meera Nair\nmeera@example.com\n\nTechnical Skills\nPython, FastAPI\n\n"
                    "Experience\nBackend engineer at CloudKettle | 2024 - Present\n"
                    "- Built FastAPI services with PostgreSQL.\n"
                ).encode(),
                "text/plain",
            )
        },
        headers=auth,
    )
    assert response.status_code == 200, response.text
    body = client.get("/api/jobs/pool/insights", headers=auth).json()
    assert body["jobs_scored"] == 0
    assert "empty" in body["message"].lower()


def test_combined_roadmap_for_pool(client):
    auth = _auth(client, _email())
    _setup(client, auth)

    response = client.post(
        "/api/skill-gaps/generate-for-pool", json={"max_skills": 5}, headers=auth
    )
    assert response.status_code == 200, response.text
    gap = response.json()
    assert gap["compatibility_id"] > 0
    assert gap["jobs_scored"] == 3
    assert len(gap["tasks"]) <= 5
    assert gap["tasks"], "combined roadmap must contain tasks"
    assert gap["skill_unlocks"], "response should explain what each task unlocks"


def test_tailor_orders_bullets_and_writes_letter(client):
    auth = _auth(client, _email())
    _setup(client, auth)
    pool = client.get("/api/jobs/pool", headers=auth).json()["jobs"]
    backend_job = next(j for j in pool if j["title"] == "Backend Engineer")

    response = client.post(f"/api/jobs/tailor?job_id={backend_job['id']}", headers=auth)
    assert response.status_code == 200, response.text
    tailor = response.json()

    assert tailor["job"]["title"] == "Backend Engineer"
    assert 0 <= tailor["fit_score"] <= 100
    assert tailor["bullets"], "bullets must be produced"
    # The bullet that evidences the job's core stack must rank first.
    assert tailor["bullets"][0]["matched_skills"], "top bullet should tag matched skills"
    assert "FastAPI" in str(tailor["bullets"][0]["matched_skills"]) or "fastapi" in str(
        tailor["bullets"][0]["matched_skills"]
    ).lower()
    assert "Dear" in tailor["cover_letter"]
    assert "Streamline" in tailor["cover_letter"]
    assert tailor["summary"]["bullet_pool"] >= 1


def test_tailor_export_html_and_md(client):
    auth = _auth(client, _email())
    _setup(client, auth)
    job = client.get("/api/jobs/pool", headers=auth).json()["jobs"][0]

    html = client.get(f"/api/jobs/tailor/export?job_id={job['id']}&format=html", headers=auth)
    assert html.status_code == 200, html.text
    assert "text/html" in html.headers["content-type"]
    assert "Tailored application" in html.text

    md = client.get(f"/api/jobs/tailor/export?job_id={job['id']}&format=md", headers=auth)
    assert md.status_code == 200, md.text
    assert "text/markdown" in md.headers["content-type"]
    assert "## Cover letter" in md.text


def test_tailor_requires_own_pool_job(client):
    auth_a = _auth(client, _email())
    auth_b = _auth(client, _email())
    _setup(client, auth_a)
    job = client.get("/api/jobs/pool", headers=auth_a).json()["jobs"][0]

    assert client.post(f"/api/jobs/tailor?job_id={job['id']}", headers=auth_b).status_code == 404
    assert (
        client.get(f"/api/jobs/tailor/export?job_id={job['id']}", headers=auth_b).status_code == 404
    )
