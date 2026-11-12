"""Request bodies for the API."""
from __future__ import annotations

from pydantic import BaseModel, Field


class JobAnalyzeRequest(BaseModel):
    description: str = ""
    url: str = ""
    title: str = ""


class CompatibilityAnalyzeRequest(BaseModel):
    resume_id: int | None = None
    job_id: int | None = None
    job_description: str = ""
    run_gap_analysis: bool = True


class AnalysisRunRequest(BaseModel):
    resume_id: int | None = None
    job_id: int | None = None
    job_description: str = ""


class GapGenerateRequest(BaseModel):
    compatibility_id: int


class TaskUpdateRequest(BaseModel):
    completed: bool


class InterviewCreateRequest(BaseModel):
    compatibility_id: int | None = None
    role: str = ""
    question_limit: int = Field(default=8, ge=3, le=15)
    kind: str = "mock"


class InterviewPrepRequest(BaseModel):
    compatibility_id: int | None = None
    limit: int = Field(default=14, ge=5, le=25)


class InterviewAnswerRequest(BaseModel):
    answer: str = Field(min_length=0, max_length=8000)


class ProviderTestRequest(BaseModel):
    provider: str
    model: str | None = None


class RoutingUpdateRequest(BaseModel):
    default_provider: str | None = None
    agent_overrides: dict[str, dict[str, str]] | None = None
    allow_paid_fallback: bool | None = None


class ProviderConfigBody(BaseModel):
    provider: str
    enabled: bool | None = None
    api_key: str | None = None
    clear_api_key: bool = False
    base_url: str | None = None
    model: str | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=64, le=32000)
    is_paid: bool | None = None
    agent_overrides: dict[str, dict[str, str]] | None = None
    default_provider: str | None = None
