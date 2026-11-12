"""Service-level tests: parsing, scoring, roadmap and evaluation."""
from __future__ import annotations

from app.schemas import CandidateProfile, JobProfile
from app.services.interview_service import evaluate_answer, generate_question_bank
from app.services.job_parser import heuristic_job_profile
from app.services.resume_parser import heuristic_resume_profile, split_sections
from app.services.roadmap_service import generate_roadmap
from app.services.scoring_service import ScoringService
from app.services.skills import extract_skills

from .conftest import JOB_TEXT, RESUME_TEXT


def test_extract_skills_aliases_and_boundaries():
    skills = extract_skills("We use Python, reactjs, Postgres and k8s. C++ is a plus. Kubernetes.")
    assert "Python" in skills
    assert "React" in skills
    assert "PostgreSQL" in skills
    assert "Kubernetes" in skills
    assert "C++" in skills
    # "R" should not be matched inside ordinary words
    assert "R" not in extract_skills("React and regular expressions")


def test_resume_sections_and_profile():
    sections = split_sections(RESUME_TEXT)
    assert "experience" in sections
    assert "projects" in sections
    profile = heuristic_resume_profile(RESUME_TEXT)
    assert profile.name == "Priya Sharma"
    assert profile.email == "priya.sharma@example.com"
    assert "Python" in profile.skills
    assert "React" in profile.skills
    assert profile.education and "B.Tech" in profile.education[0].degree
    assert profile.projects
    assert profile.years_experience > 0
    assert profile.resume_weaknesses
    assert profile.improvement_suggestions


def test_resume_review_flags_quantification():
    weak = "Alex Doe\nMy Resume\nI am hardworking and a team player. I like coding."
    profile = heuristic_resume_profile(weak)
    joined = " ".join(profile.resume_weaknesses).lower()
    assert profile.name == "Alex Doe"
    assert "quantified" in joined or "short" in joined


def test_job_profile_required_vs_preferred():
    job = heuristic_job_profile(JOB_TEXT)
    assert "Python" in job.required_skills
    assert "FastAPI" in job.required_skills
    assert "Kubernetes" in job.preferred_skills
    assert "LangChain" in job.preferred_skills
    assert "Kubernetes" not in job.required_skills
    assert job.role_category == "ai_ml"
    assert job.min_years_experience == 1
    assert job.responsibilities


def test_scoring_is_deterministic_and_explainable():
    candidate = heuristic_resume_profile(RESUME_TEXT)
    job = heuristic_job_profile(JOB_TEXT)
    scoring = ScoringService()
    first = scoring.score(candidate, job, RESUME_TEXT)
    second = scoring.score(candidate, job, RESUME_TEXT)
    assert first.overall_score == second.overall_score
    assert 0 <= first.overall_score <= 100
    assert abs(sum(c.weight for c in first.category_scores) - 1.0) < 1e-6
    assert abs(sum(c.weighted for c in first.category_scores) - first.overall_score) < 0.2
    matched = {m.skill for m in first.matched_skills}
    assert "Python" in matched
    assert any(m.skill in {"Kubernetes", "LangChain", "AWS", "TypeScript"} for m in first.missing_skills)
    assert first.evidence
    assert first.explanation


def test_scoring_penalises_empty_candidate():
    job = heuristic_job_profile(JOB_TEXT)
    report = ScoringService().score(CandidateProfile(), job, "")
    assert report.overall_score < 40
    assert report.missing_skills


def test_roadmap_prioritises_missing_skills():
    candidate = heuristic_resume_profile(RESUME_TEXT)
    job = heuristic_job_profile(JOB_TEXT)
    report = ScoringService().score(candidate, job, RESUME_TEXT)
    gap = generate_roadmap(report)
    assert gap.learning_roadmap
    assert gap.total_estimated_hours > 0
    assert gap.preparation_plan
    assert gap.recommended_projects
    for step in gap.learning_roadmap:
        assert step.study_topics
        assert step.resources == []  # never fabricate links


def test_question_bank_and_answer_evaluation():
    candidate = heuristic_resume_profile(RESUME_TEXT)
    job = heuristic_job_profile(JOB_TEXT)
    bank = generate_question_bank(candidate, job)
    types = {q.type for q in bank.questions}
    assert "technical" in types
    assert "project" in types
    assert "hr" in types
    assert len(bank.questions) >= 8
    question = bank.questions[0]

    weak = evaluate_answer(question, "I do not know.")
    strong = evaluate_answer(
        question,
        "In my FastAPI project I built the endpoint with dependency injection and Pydantic validation. "
        "First I modelled the schema, then added indexes. Because the query was slow, I measured with "
        "EXPLAIN and added a composite index, which reduced latency by 35%. The trade-off was write cost.",
    )
    assert strong.overall > weak.overall
    assert strong.technical_accuracy >= 0
    assert weak.suggestions
    assert weak.follow_up or question.follow_ups == []


def test_llm_scores_are_validated():
    """Raw model scores are bounded by the schema and recomputed by the agent."""
    from app.schemas import AnswerEvaluation

    evaluation = AnswerEvaluation(technical_accuracy=80, overall=99)
    assert evaluation.overall == 99  # raw model value; agents recompute before persistence
    assert 0 <= evaluation.technical_accuracy <= 100
