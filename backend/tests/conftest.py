"""Test setup: isolate the database before importing the app."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="recruimate-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP / 'test.db'}"
os.environ["UPLOAD_DIR"] = str(_TMP / "uploads")
os.environ["DEFAULT_PROVIDER"] = "heuristic"
os.environ["EMBEDDINGS_BACKEND"] = "hashed"
# The suite targets trusted-local mode and must not depend on the developer's
# own .env (which may enable auth/accounts).
os.environ["AUTH_ENABLED"] = "false"
os.environ["SEED_DEMO_ACCOUNTS"] = "false"
# PyJWT warns when an HS256 key is shorter than 32 bytes; give tests a real
# length secret so the suite is not drowned in key-length warnings.
os.environ["JWT_SECRET"] = "test-only-secret-" + "0" * 40
for key in (
    "OPENROUTER_API_KEY",
    "GROQ_API_KEY",
    "GEMINI_API_KEY",
    "OPENCODE_PASSWORD",
    "API_TOKEN",
):
    os.environ[key] = ""

import pytest  # noqa: E402
import sys  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

RESUME_TEXT = """Priya Sharma
priya.sharma@example.com | +91 98765 43210 | github.com/priyasharma | Bengaluru

Professional Summary
Final-year computer science student and backend-focused developer with internship
experience building FastAPI services and React dashboards. Interested in applied AI.

Technical Skills
Python, JavaScript, React, FastAPI, PostgreSQL, Docker, Git, Pandas, NumPy, REST APIs

Experience
Software Engineering Intern at Nimbus Labs | Jan 2025 - Jun 2025
- Built REST APIs with FastAPI and PostgreSQL for an internal analytics tool.
- Reduced average response time by 35% by adding indexes and caching.
- Wrote pytest tests and containerised the service with Docker.

Projects
RecruiMate - AI interview coach
- Built a React dashboard and FastAPI backend that analyses resumes against job posts.
- Implemented deterministic compatibility scoring and a mock interview workflow.

Education
B.Tech in Computer Science, VIT Vellore, 2021 - 2025

Certifications
AWS Certified Cloud Practitioner
"""

JOB_TEXT = """AI Engineer (Entry Level)
Nimbus Labs | Bengaluru | Full-time

About the role
We are looking for an early-career AI engineer to build candidate-facing products.

Responsibilities
- Build retrieval-augmented generation pipelines for document understanding.
- Develop and maintain FastAPI services and React interfaces.
- Work with PostgreSQL, Docker and CI/CD in a small product team.
- Evaluate model outputs and improve answer quality.

Requirements
- Strong Python programming skills.
- Experience with FastAPI, REST APIs, React and PostgreSQL.
- Familiarity with Docker, Git and unit testing.
- 1+ years of relevant experience through internships or projects.
- Bachelor's degree in Computer Science or a related field.

Preferred
- Kubernetes, AWS, LangChain, TypeScript and vector databases.
"""


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def uploaded_resume(client):
    response = client.post(
        "/api/resume/upload",
        files={"file": ("priya_resume.txt", RESUME_TEXT.encode(), "text/plain")},
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture(scope="session")
def analyzed_job(client):
    response = client.post("/api/jobs/analyze", json={"description": JOB_TEXT})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture(scope="session")
def compatibility(client, uploaded_resume, analyzed_job):
    response = client.post(
        "/api/compatibility/analyze",
        json={"resume_id": uploaded_resume["id"], "job_id": analyzed_job["id"]},
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture(scope="session")
def tmp_root():
    return _TMP
