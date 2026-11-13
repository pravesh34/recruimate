"""SQLAlchemy models and session handling.

One local candidate account is seeded for the single-user MVP; the models already
carry user_id so authentication can be layered on without a schema migration.
"""
from __future__ import annotations

import datetime as dt
from typing import Generator

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from ..config import settings


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, default="candidate@local")
    display_name: Mapped[str] = mapped_column(String(120), default="Candidate")
    is_local: Mapped[bool] = mapped_column(Boolean, default=True)

    # --- Authentication -----------------------------------------------------
    # Null password_hash means "trusted local" account with no password.
    password_hash: Mapped[str] = mapped_column(String(255), default="")
    role: Mapped[str] = mapped_column(String(32), default="candidate")  # candidate|admin
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


class AuthSession(Base, TimestampMixin):
    """Refresh-token ledger. Access tokens are stateless JWTs; refresh tokens
    are opaque, hashed at rest and revocable per row."""

    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    user_agent: Mapped[str] = mapped_column(String(512), default="")
    ip_address: Mapped[str] = mapped_column(String(64), default="")
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime)
    revoked_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped[User] = relationship("User")


class ResumeProfile(Base, TimestampMixin):
    __tablename__ = "resume_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255), default="")
    storage_path: Mapped[str] = mapped_column(String(1024), default="")
    raw_text: Mapped[str] = mapped_column(Text, default="")
    profile: Mapped[dict] = mapped_column(JSON, default=dict)
    provider: Mapped[str] = mapped_column(String(64), default="heuristic")


class JobAnalysis(Base, TimestampMixin):
    __tablename__ = "job_analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    company: Mapped[str] = mapped_column(String(255), default="")
    source_url: Mapped[str] = mapped_column(String(1024), default="")
    raw_text: Mapped[str] = mapped_column(Text, default="")
    profile: Mapped[dict] = mapped_column(JSON, default=dict)
    provider: Mapped[str] = mapped_column(String(64), default="heuristic")


class JobPosting(Base, TimestampMixin):
    """Imported job-board posting used by the job-search ranking feature.

    Unlike :class:`JobAnalysis` (a pasted/analysed description), postings come
    from an import pipeline or the demo seeder. ``parsed`` holds structured
    skills/experience so the deterministic compatibility agent can score
    against them without an LLM call.
    """

    __tablename__ = "job_postings"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), index=True, nullable=True
    )
    source: Mapped[str] = mapped_column(String(64), default="")
    url: Mapped[str] = mapped_column(String(1024), default="")
    title: Mapped[str] = mapped_column(String(255), default="")
    company: Mapped[str] = mapped_column(String(255), default="")
    location: Mapped[str] = mapped_column(String(255), default="")
    raw_text: Mapped[str] = mapped_column(Text, default="")
    parsed: Mapped[dict] = mapped_column(JSON, default=dict)
    provider: Mapped[str] = mapped_column(String(64), default="heuristic")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")


class CompatibilityReport(Base, TimestampMixin):
    __tablename__ = "compatibility_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    resume_id: Mapped[int] = mapped_column(ForeignKey("resume_profiles.id"), index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("job_analyses.id"), index=True)
    overall_score: Mapped[float] = mapped_column(Float, default=0.0)
    report: Mapped[dict] = mapped_column(JSON, default=dict)


class SkillGapReport(Base, TimestampMixin):
    __tablename__ = "skill_gap_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    compatibility_id: Mapped[int] = mapped_column(ForeignKey("compatibility_reports.id"), index=True)
    report: Mapped[dict] = mapped_column(JSON, default=dict)

    tasks: Mapped[list["LearningTask"]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )


class LearningTask(Base, TimestampMixin):
    __tablename__ = "learning_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("skill_gap_reports.id"), index=True)
    skill: Mapped[str] = mapped_column(String(120), default="")
    title: Mapped[str] = mapped_column(String(255), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    estimated_hours: Mapped[float] = mapped_column(Float, default=2.0)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)

    report: Mapped[SkillGapReport] = relationship(back_populates="tasks")


class InterviewSession(Base, TimestampMixin):
    __tablename__ = "interview_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    compatibility_id: Mapped[int | None] = mapped_column(
        ForeignKey("compatibility_reports.id"), nullable=True
    )
    role: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(32), default="active")  # active|completed
    kind: Mapped[str] = mapped_column(String(32), default="mock")  # mock|prep
    provider: Mapped[str] = mapped_column(String(64), default="")
    state: Mapped[dict] = mapped_column(JSON, default=dict)
    report: Mapped[dict] = mapped_column(JSON, default=dict)

    messages: Mapped[list["InterviewMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="InterviewMessage.id"
    )
    evaluations: Mapped[list["InterviewEvaluation"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class InterviewMessage(Base, TimestampMixin):
    __tablename__ = "interview_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("interview_sessions.id"), index=True)
    role: Mapped[str] = mapped_column(String(16), default="assistant")  # assistant|candidate|system
    content: Mapped[str] = mapped_column(Text, default="")
    meta: Mapped[dict] = mapped_column(JSON, default=dict)

    session: Mapped[InterviewSession] = relationship(back_populates="messages")


class InterviewEvaluation(Base, TimestampMixin):
    __tablename__ = "interview_evaluations"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("interview_sessions.id"), index=True)
    question: Mapped[str] = mapped_column(Text, default="")
    answer: Mapped[str] = mapped_column(Text, default="")
    scores: Mapped[dict] = mapped_column(JSON, default=dict)
    feedback: Mapped[str] = mapped_column(Text, default="")
    suggestions: Mapped[list] = mapped_column(JSON, default=list)

    session: Mapped[InterviewSession] = relationship(back_populates="evaluations")


class AppSetting(Base, TimestampMixin):
    """Small key/value store for routing preferences (default provider, per-agent models)."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)


class ProviderConfiguration(Base, TimestampMixin):
    __tablename__ = "provider_configurations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    provider: Mapped[str] = mapped_column(String(64), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    api_key: Mapped[str] = mapped_column(Text, default="")
    base_url: Mapped[str] = mapped_column(String(1024), default="")
    model: Mapped[str] = mapped_column(String(255), default="")
    temperature: Mapped[float] = mapped_column(Float, default=0.3)
    max_tokens: Mapped[int] = mapped_column(Integer, default=1500)
    is_paid: Mapped[bool] = mapped_column(Boolean, default=False)
    # Per-agent override: {"resume_agent": {"provider": "...", "model": "..."}}
    agent_overrides: Mapped[dict] = mapped_column(JSON, default=dict)


class UsageLog(Base, TimestampMixin):
    __tablename__ = "usage_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    provider: Mapped[str] = mapped_column(String(64), default="")
    model: Mapped[str] = mapped_column(String(255), default="")
    agent: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(32), default="ok")
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")


engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _apply_column_migrations()
    with SessionLocal() as db:
        user = db.query(User).first()
        if not user:
            db.add(User(email="candidate@local", display_name="Candidate"))
            db.commit()


# Columns added after the first release. `create_all` only creates missing
# tables, so new columns on existing tables need an explicit ALTER.
_ADDED_COLUMNS: dict[str, dict[str, str]] = {
    "users": {
        "password_hash": "VARCHAR(255) NOT NULL DEFAULT ''",
        "role": "VARCHAR(32) NOT NULL DEFAULT 'candidate'",
        "is_active": "BOOLEAN NOT NULL DEFAULT 1",
        "is_demo": "BOOLEAN NOT NULL DEFAULT 0",
        "last_login_at": "DATETIME",
    },
}


def _apply_column_migrations() -> None:
    """Add columns introduced after the schema was first created.

    Kept deliberately small: this is a single-user local app with a SQLite
    file, so a handful of ALTER TABLE statements is cheaper than pulling in a
    full migration framework.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    for table, columns in _ADDED_COLUMNS.items():
        if table not in existing_tables:
            continue
        present = {col["name"] for col in inspector.get_columns(table)}
        for name, ddl in columns.items():
            if name in present:
                continue
            try:
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
            except Exception:  # pragma: no cover - column may already exist
                continue


def ensure_default_user(db) -> User:
    user = db.query(User).first()
    if not user:
        user = User(email="candidate@local", display_name="Candidate")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user
