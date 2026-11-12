"""Pydantic schemas used by agents, the gateway and the API."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------- resume / job
class EducationItem(BaseModel):
    institution: str = ""
    degree: str = ""
    field: str = ""
    start_year: str = ""
    end_year: str = ""
    details: str = ""


class ExperienceItem(BaseModel):
    company: str = ""
    title: str = ""
    start: str = ""
    end: str = ""
    description: str = ""
    highlights: list[str] = Field(default_factory=list)


class ProjectItem(BaseModel):
    name: str = ""
    description: str = ""
    technologies: list[str] = Field(default_factory=list)


class CandidateProfile(BaseModel):
    name: str = ""
    headline: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    soft_skills: list[str] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    experience: list[ExperienceItem] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    resume_strengths: list[str] = Field(default_factory=list)
    resume_weaknesses: list[str] = Field(default_factory=list)
    improvement_suggestions: list[str] = Field(default_factory=list)
    unknown_fields: list[str] = Field(default_factory=list)
    years_experience: float = 0.0


class JobProfile(BaseModel):
    job_title: str = ""
    company: str = ""
    location: str = ""
    employment_type: str = ""
    role_category: str = "general"
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    experience_requirements: list[str] = Field(default_factory=list)
    education_requirements: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    behavioural_expectations: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    min_years_experience: float = 0.0


# ---------------------------------------------------------------- compatibility
class SkillMatch(BaseModel):
    skill: str = ""
    matched_with: str = ""
    similarity: float = 0.0
    status: Literal["matched", "partial", "missing"] = "missing"
    evidence: str = ""


class CategoryScore(BaseModel):
    name: str
    score: float
    weight: float
    weighted: float
    explanation: str


class CompatibilityReport(BaseModel):
    overall_score: float
    verdict: str
    category_scores: list[CategoryScore]
    matched_skills: list[SkillMatch] = Field(default_factory=list)
    partially_matched_skills: list[SkillMatch] = Field(default_factory=list)
    missing_skills: list[SkillMatch] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    explanation: str = ""
    strengths: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    method: str = "deterministic+embeddings"


# ---------------------------------------------------------------- gap analysis
class RoadmapStep(BaseModel):
    order: int = 1
    skill: str = ""
    title: str = ""
    description: str = ""
    study_topics: list[str] = Field(default_factory=list)
    practice_project: str = ""
    estimated_hours: float = 2.0
    priority: Literal["high", "medium", "low"] = "medium"
    resources: list[str] = Field(default_factory=list)


class GapAnalysisReport(BaseModel):
    summary: str = ""
    priority_skills: list[str] = Field(default_factory=list)
    learning_roadmap: list[RoadmapStep] = Field(default_factory=list)
    recommended_projects: list[str] = Field(default_factory=list)
    study_topics: list[str] = Field(default_factory=list)
    preparation_plan: list[str] = Field(default_factory=list)
    total_estimated_hours: float = 0.0


# ---------------------------------------------------------------- interview prep
QuestionType = Literal["technical", "project", "hr", "behavioural", "problem_solving"]


class InterviewQuestion(BaseModel):
    id: str = ""
    type: QuestionType = "technical"
    question: str = ""
    why_asked: str = ""
    expected_points: list[str] = Field(default_factory=list)
    follow_ups: list[str] = Field(default_factory=list)
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    related_skill: str = ""


class QuestionBank(BaseModel):
    questions: list[InterviewQuestion] = Field(default_factory=list)


class AnswerEvaluation(BaseModel):
    technical_accuracy: float = 0
    conceptual_understanding: float = 0
    communication: float = 0
    problem_solving: float = 0
    relevance: float = 0
    completeness: float = 0
    overall: float = 0
    feedback: str = ""
    suggestions: list[str] = Field(default_factory=list)
    follow_up: str = ""


class InterviewReport(BaseModel):
    overall_performance: float = 0
    readiness: str = ""
    summary: str = ""
    strengths: list[str] = Field(default_factory=list)
    improvement_areas: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    answered_questions: int = 0


# ---------------------------------------------------------------- gateway
class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class GatewayRequest(BaseModel):
    messages: list[ChatMessage]
    model: str | None = None
    temperature: float = 0.3
    max_tokens: int = 1500
    json_mode: bool = False
    agent: str = "supervisor"


class GatewayResponse(BaseModel):
    content: str
    provider: str
    model: str
    latency_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    raw: dict[str, Any] | None = None


class ProviderHealth(BaseModel):
    provider: str
    configured: bool
    healthy: bool
    detail: str = ""
    latency_ms: float = 0.0
    model: str = ""


class ProviderInfo(BaseModel):
    provider: str
    label: str
    enabled: bool
    configured: bool
    base_url: str = ""
    model: str = ""
    is_paid: bool = False
    api_key_set: bool = False
    api_key_hint: str = ""
    health: ProviderHealth | None = None
    models: list[str] = Field(default_factory=list)
    note: str = ""


class ProviderConfigurationUpdate(BaseModel):
    provider: str
    enabled: bool | None = None
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=64, le=32000)
    is_paid: bool | None = None
    agent_overrides: dict[str, dict[str, str]] | None = None
