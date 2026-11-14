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
    # Target-pool posting id (job_postings row). Mirrored into job_analyses
    # before scoring so history/analytics treat it like any other analysis.
    pool_job_id: int | None = None
    run_gap_analysis: bool = True


class AnalysisRunRequest(BaseModel):
    resume_id: int | None = None
    job_id: int | None = None
    job_description: str = ""
    pool_job_id: int | None = None


class GapGenerateRequest(BaseModel):
    compatibility_id: int


class GapForJobRequest(BaseModel):
    """Generate a plan-of-approach roadmap against a target-pool posting."""

    resume_id: int | None = None
    job_id: int
    track_tasks: bool = True


class PoolImportRequest(BaseModel):
    """Import real postings from a job board into the caller's target pool."""

    source: str = Field(default="remotive")
    query: str = Field(default="", max_length=120)
    limit: int = Field(default=12, ge=1, le=50)


class CliSearchRequest(BaseModel):
    """A read-only Jobs CLI search."""

    query: str = Field(default="", max_length=200)
    location: str = Field(default="", max_length=200)
    sources: list[str] = Field(default_factory=list, max_length=5)
    remote: bool = False
    limit: int = Field(default=25, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=10000)
    country: str = Field(default="", max_length=8)


class CliImportRequest(BaseModel):
    """Selected CLI listings to add to the caller's pool."""

    listings: list[dict] = Field(default_factory=list, max_length=100)


class CliTrackRequest(BaseModel):
    """Bookmark / application-tracking payload."""

    job_posting_id: int | None = None
    status: str = Field(default="", max_length=32)
    note: str = Field(default="", max_length=4000)


class PoolSingleRequest(BaseModel):
    """Persist one browsed listing into the caller's pool."""

    title: str = Field(min_length=1, max_length=255)
    company: str = Field(default="", max_length=255)
    location: str = Field(default="", max_length=255)
    url: str = Field(min_length=1, max_length=1024)
    source: str = Field(default="manual", max_length=64)
    tags: list[str] = Field(default_factory=list)
    description: str = Field(default="", max_length=40000)


class PoolAddRequest(BaseModel):
    """Add one job to the pool from a URL or pasted description."""

    url: str = ""
    description: str = ""
    title: str = ""
    company: str = ""
    location: str = ""


class PoolGapGenerateRequest(BaseModel):
    """One combined roadmap across the whole target job pool."""

    resume_id: int | None = None
    max_skills: int = Field(default=6, ge=3, le=8)


class InterviewForJobRequest(BaseModel):
    """Start a mock interview against a target-pool posting."""

    resume_id: int | None = None
    job_id: int
    question_limit: int = Field(default=8, ge=3, le=15)


class PipelineCreate(BaseModel):
    """Track a job in the application pipeline (from the pool or manual)."""

    job_id: int | None = None
    title: str = Field(default="", max_length=255)
    company: str = Field(default="", max_length=255)
    url: str = Field(default="", max_length=1024)
    source: str = Field(default="", max_length=64)
    status: str = ""
    notes: str = Field(default="", max_length=4000)


class PipelineUpdate(BaseModel):
    status: str | None = None
    notes: str | None = Field(default=None, max_length=4000)
    next_action_at: str | None = None


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


class JobMatch(BaseModel):
    job_id: int
    title: str
    company: str
    location: str
    remote: bool
    compatibility_score: float
    match_reasons: dict = Field(default_factory=dict)


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
