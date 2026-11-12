"""End-to-end API tests using the deterministic heuristic provider."""
from __future__ import annotations


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_resume_upload_and_profile(client, uploaded_resume):
    assert uploaded_resume["profile"]["name"] == "Priya Sharma"
    assert uploaded_resume["provider"] == "heuristic"
    profile = client.get("/api/resume/profile")
    assert profile.status_code == 200
    assert profile.json()["id"] == uploaded_resume["id"]


def test_invalid_upload_rejected(client):
    response = client.post(
        "/api/resume/upload",
        files={"file": ("resume.exe", b"not a resume" * 20, "application/octet-stream")},
    )
    assert response.status_code == 400


def test_job_analysis(analyzed_job):
    assert analyzed_job["profile"]["required_skills"]
    assert analyzed_job["title"]


def test_job_url_blocks_private_hosts(client):
    response = client.post("/api/jobs/analyze", json={"url": "http://127.0.0.1:8000/secret"})
    assert response.status_code == 400
    assert "Unsafe" in response.json()["detail"]


def test_compatibility_and_gap(client, compatibility):
    assert 0 <= compatibility["overall_score"] <= 100
    assert compatibility["report"]["category_scores"]
    assert compatibility["gap"] is not None
    assert compatibility["gap"]["tasks"]
    gap_id = compatibility["gap"]["id"]
    gap = client.get(f"/api/skill-gaps/{gap_id}")
    assert gap.status_code == 200
    assert gap.json()["report"]["priority_skills"]


def test_task_completion_updates_progress(client, compatibility):
    gap = compatibility["gap"]
    task = gap["tasks"][0]
    response = client.patch(f"/api/skill-gaps/tasks/{task['id']}", json={"completed": True})
    assert response.status_code == 200
    updated = response.json()
    assert updated["progress"]["completed"] >= 1
    # revert so later dashboard assertions stay stable
    client.patch(f"/api/skill-gaps/tasks/{task['id']}", json={"completed": False})


def test_full_supervisor_run(client, uploaded_resume, analyzed_job):
    response = client.post(
        "/api/analysis/run",
        json={"resume_id": uploaded_resume["id"], "job_id": analyzed_job["id"]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["report"]["overall_score"] > 0
    assert body["gap"]["report"]["learning_roadmap"]
    assert body["questions"]["questions"]
    assert body["activity"]
    assert body["providers"]["resume_agent"] == "heuristic"
    assert body["engine"] in {"langgraph", "async-fallback"}


def test_interview_prep_and_mock_flow(client, compatibility):
    prep = client.post("/api/interviews/prep", json={"compatibility_id": compatibility["id"]})
    assert prep.status_code == 200
    questions = prep.json()["questions"]
    assert len(questions) >= 8
    assert any(q["type"] == "technical" for q in questions)

    created = client.post(
        "/api/interviews",
        json={"compatibility_id": compatibility["id"], "question_limit": 4},
    )
    assert created.status_code == 200, created.text
    session = created.json()
    assert session["status"] == "active"
    assert session["current_question"]
    assert session["messages"][-1]["role"] == "assistant"
    session_id = session["id"]

    answered = client.post(
        f"/api/interviews/{session_id}/answer",
        json={
            "answer": (
                "In my internship I built a FastAPI service with PostgreSQL. First I clarified the "
                "requirements, then designed the schema and added indexes. Because latency was high, "
                "I measured with EXPLAIN and reduced response time by 35%. The trade-off was extra write cost."
            )
        },
    )
    assert answered.status_code == 200, answered.text
    body = answered.json()
    assert body["evaluation"]["overall"] > 0
    assert body["session"]["progress"]["answered"] == 1

    finished = client.post(f"/api/interviews/{session_id}/complete")
    assert finished.status_code == 200
    final = finished.json()
    assert final["status"] == "completed"
    assert final["report"]["overall_performance"] > 0
    history = client.get("/api/interviews")
    assert history.status_code == 200
    assert any(item["id"] == session_id for item in history.json())


def test_dashboard_and_analytics(client):
    dashboard = client.get("/api/dashboard")
    assert dashboard.status_code == 200
    data = dashboard.json()
    assert data["candidate"]["name"] == "Priya Sharma"
    assert data["stats"]["analysis_count"] >= 1
    assert data["stats"]["interview_count"] >= 1

    analytics = client.get("/api/analytics")
    assert analytics.status_code == 200
    body = analytics.json()
    assert body["compatibility_history"]
    assert body["category_averages"]


def test_providers_and_routing(client):
    providers = client.get("/api/providers")
    assert providers.status_code == 200
    body = providers.json()
    names = {p["provider"] for p in body["providers"]}
    assert {"heuristic", "openrouter", "groq", "gemini", "opencode", "ollama"} <= names
    assert all("api_key" not in p for p in body["providers"])
    assert body["routing"]["default_provider"] == "heuristic"

    routing = client.put(
        "/api/providers/routing",
        json={
            "default_provider": "heuristic",
            "agent_overrides": {"resume_agent": {"provider": "heuristic", "model": ""}},
        },
    )
    assert routing.status_code == 200
    assert routing.json()["routing"]["agent_overrides"]["resume_agent"]["provider"] == "heuristic"

    bad = client.put(
        "/api/providers/configuration",
        json={"provider": "custom", "base_url": "http://169.254.169.254/latest", "enabled": True},
    )
    assert bad.status_code == 400


def test_provider_health(client):
    response = client.get("/api/providers/health")
    assert response.status_code == 200
    health = {p["provider"]: p for p in response.json()["providers"]}
    assert health["heuristic"]["healthy"] is True
    assert health["openrouter"]["configured"] is False


def test_interview_answer_requires_compatibility(client):
    response = client.post("/api/interviews", json={"compatibility_id": 99999})
    assert response.status_code == 404
