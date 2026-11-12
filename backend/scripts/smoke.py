"""End-to-end smoke test with no network and no API keys.

Run from backend/:  .venv/bin/python scripts/smoke.py
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix="recruimate-smoke-"))
os.environ["DATABASE_URL"] = f"sqlite:///{TMP / 'smoke.db'}"
os.environ["UPLOAD_DIR"] = str(TMP / "uploads")
os.environ["DEFAULT_PROVIDER"] = "heuristic"
os.environ["EMBEDDINGS_BACKEND"] = "hashed"

import sys  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

RESUME = """Priya Sharma
priya.sharma@example.com | +91 98765 43210 | github.com/priyasharma | Bengaluru

Professional Summary
Final-year computer science student and backend-focused developer with internship
experience building FastAPI services and React dashboards.

Technical Skills
Python, JavaScript, React, FastAPI, PostgreSQL, Docker, Git, Pandas, NumPy, REST APIs

Experience
Software Engineering Intern at Nimbus Labs | Jan 2025 - Jun 2025
- Built REST APIs with FastAPI and PostgreSQL for an internal analytics tool.
- Reduced average response time by 35% by adding indexes and caching.

Projects
RecruiMate - AI interview coach
- Built a React dashboard and FastAPI backend with deterministic compatibility scoring.

Education
B.Tech in Computer Science, VIT Vellore, 2021 - 2025

Certifications
AWS Certified Cloud Practitioner
"""

JOB = """AI Engineer (Entry Level)
Nimbus Labs | Bengaluru | Full-time

Responsibilities
- Build retrieval-augmented generation pipelines.
- Develop FastAPI services and React interfaces.
- Work with PostgreSQL, Docker and CI/CD.

Requirements
- Strong Python programming skills.
- Experience with FastAPI, REST APIs, React and PostgreSQL.
- Familiarity with Docker, Git and unit testing.
- 1+ years of relevant experience.

Preferred
- Kubernetes, AWS, LangChain, TypeScript and vector databases.
"""


def main() -> None:
    with TestClient(app) as client:
        health = client.get("/api/health").json()
        print("health:", health["status"], "| embeddings:", health["embeddings"])

        resume = client.post(
            "/api/resume/upload",
            files={"file": ("priya.txt", RESUME.encode(), "text/plain")},
        )
        assert resume.status_code == 200, resume.text
        resume_data = resume.json()
        print("resume:", resume_data["profile"]["name"], "| skills:", len(resume_data["profile"]["skills"]), "| provider:", resume_data["provider"])

        job = client.post("/api/jobs/analyze", json={"description": JOB})
        assert job.status_code == 200, job.text
        job_data = job.json()
        print("job:", job_data["title"], "| required:", job_data["profile"]["required_skills"][:4])

        compat = client.post(
            "/api/compatibility/analyze",
            json={"resume_id": resume_data["id"], "job_id": job_data["id"]},
        )
        assert compat.status_code == 200, compat.text
        compat_data = compat.json()
        print("compatibility:", compat_data["overall_score"], compat_data["report"]["verdict"], "| gaps:", compat_data["gap"]["report"]["priority_skills"][:3])

        full = client.post(
            "/api/analysis/run",
            json={"resume_id": resume_data["id"], "job_id": job_data["id"]},
        )
        assert full.status_code == 200, full.text
        full_data = full.json()
        print("workflow:", full_data["engine"], "| activity:", len(full_data["activity"]), "| questions:", len(full_data["questions"]["questions"]))

        prep = client.post("/api/interviews/prep", json={"compatibility_id": full_data["id"]})
        assert prep.status_code == 200, prep.text
        print("prep questions:", len(prep.json()["questions"]))

        session = client.post(
            "/api/interviews",
            json={"compatibility_id": full_data["id"], "question_limit": 4},
        )
        assert session.status_code == 200, session.text
        session_data = session.json()
        print("interview:", session_data["id"], "| first Q:", session_data["current_question"]["question"][:80])

        answer = client.post(
            f"/api/interviews/{session_data['id']}/answer",
            json={
                "answer": (
                    "In my FastAPI internship I built a PostgreSQL-backed endpoint. First I clarified "
                    "requirements, then designed the schema and measured the query. Because latency was "
                    "high, I added a composite index and reduced response time by 35%."
                )
            },
        )
        assert answer.status_code == 200, answer.text
        print("evaluation:", answer.json()["evaluation"]["overall"], "| completed:", answer.json()["completed"])

        final = client.post(f"/api/interviews/{session_data['id']}/complete")
        assert final.status_code == 200, final.text
        print("report:", final.json()["report"]["overall_performance"], final.json()["report"]["readiness"])

        dashboard = client.get("/api/dashboard").json()
        print("dashboard:", dashboard["stats"])

        providers = client.get("/api/providers").json()
        print("providers:", [p["provider"] for p in providers["providers"]])

        print("\nSMOKE TEST PASSED")


if __name__ == "__main__":
    main()
