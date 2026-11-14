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
    UniqueConstraint,
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
    # All sessions created by one login/refresh chain share a family id, so a
    # replayed (already-rotated) refresh token can revoke the whole chain.
    family_id: Mapped[str] = mapped_column(String(64), default="", index=True)
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
    # Canonical PDF rendering of the resume (always generated from the
    # extracted text), so every candidate has one consistent document.
    pdf_path: Mapped[str] = mapped_column(String(1024), default="")
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

    # --- Jobs CLI / board import fields -------------------------------------
    # Identity of the posting on the source board and the cross-source key
    # used to stop the same role being imported twice.
    source_job_id: Mapped[str] = mapped_column(String(200), default="")
    dedupe_key: Mapped[str] = mapped_column(String(64), default="", index=True)
    apply_url: Mapped[str] = mapped_column(String(1024), default="")
    remote: Mapped[bool] = mapped_column(Boolean, default=False)
    employment_type: Mapped[str] = mapped_column(String(64), default="")
    experience_level: Mapped[str] = mapped_column(String(64), default="")
    salary_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_currency: Mapped[str] = mapped_column(String(16), default="")
    salary_text: Mapped[str] = mapped_column(String(255), default="")
    posted_at: Mapped[str] = mapped_column(String(32), default="")


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


class PipelineEntry(Base, TimestampMixin):
    """Application-pipeline entry: a target job the candidate is pursuing.

    Snapshots the posting's identity so history survives pool deletions;
    ``job_posting_id`` is a soft link (no DB cascade on purpose).
    """

    __tablename__ = "pipeline_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    job_posting_id: Mapped[int | None] = mapped_column(ForeignKey("job_postings.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    company: Mapped[str] = mapped_column(String(255), default="")
    url: Mapped[str] = mapped_column(String(1024), default="")
    source: Mapped[str] = mapped_column(String(64), default="")
    # new|shortlisted|applied|interview|offer|rejected|closed
    status: Mapped[str] = mapped_column(String(32), default="new", index=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    next_action_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    # Where the role came from and where the candidate applies (source
    # attribution + the original Apply link).
    apply_url: Mapped[str] = mapped_column(String(1024), default="")
    source_job_id: Mapped[str] = mapped_column(String(200), default="")


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


class JobBookmark(Base, TimestampMixin):
    """A job the candidate saved for later. Strictly user-scoped."""

    __tablename__ = "job_bookmarks"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    job_posting_id: Mapped[int | None] = mapped_column(
        ForeignKey("job_postings.id"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255), default="")
    company: Mapped[str] = mapped_column(String(255), default="")
    url: Mapped[str] = mapped_column(String(1024), default="")
    apply_url: Mapped[str] = mapped_column(String(1024), default="")
    source: Mapped[str] = mapped_column(String(64), default="")
    note: Mapped[str] = mapped_column(Text, default="")

    __table_args__ = (
        UniqueConstraint("user_id", "job_posting_id", name="uq_job_bookmark_user_posting"),
    )


class CliSyncRun(Base, TimestampMixin):
    """Audit trail for a background Jobs CLI synchronisation."""

    __tablename__ = "cli_sync_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    source: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(32), default="running")  # running|done|error
    imported: Mapped[int] = mapped_column(Integer, default=0)
    updated: Mapped[int] = mapped_column(Integer, default=0)
    skipped: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


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

if settings.database_url.startswith("sqlite"):
    from sqlalchemy import event as _sa_event

    def _sqlite_pragmas(dbapi_connection, _record):  # pragma: no cover - thin wrapper
        """Per-connection SQLite hardening.

        * WAL keeps readers from blocking on a writer (multi-user ready).
        * busy_timeout turns 'database is locked' into a bounded wait.
        * foreign_keys=ON enforces the FK relationships the ORM declares —
          SQLite ignores them by default, so orphan rows would otherwise be
          possible through every non-ORM write path.
        """
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

    _sa_event.listen(engine, "connect", _sqlite_pragmas)

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
        from .seed import maybe_seed

        maybe_seed(db)


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
    "auth_sessions": {
        "family_id": "VARCHAR(64) NOT NULL DEFAULT ''",
    },
    "resume_profiles": {
        "pdf_path": "VARCHAR(1024) NOT NULL DEFAULT ''",
    },
    "job_postings": {
        "source_job_id": "VARCHAR(200) NOT NULL DEFAULT ''",
        "dedupe_key": "VARCHAR(64) NOT NULL DEFAULT ''",
        "apply_url": "VARCHAR(1024) NOT NULL DEFAULT ''",
        "remote": "BOOLEAN NOT NULL DEFAULT 0",
        "employment_type": "VARCHAR(64) NOT NULL DEFAULT ''",
        "experience_level": "VARCHAR(64) NOT NULL DEFAULT ''",
        "salary_min": "FLOAT",
        "salary_max": "FLOAT",
        "salary_currency": "VARCHAR(16) NOT NULL DEFAULT ''",
        "salary_text": "VARCHAR(255) NOT NULL DEFAULT ''",
        "posted_at": "VARCHAR(32) NOT NULL DEFAULT ''",
    },
    "pipeline_entries": {
        "apply_url": "VARCHAR(1024) NOT NULL DEFAULT ''",
        "source_job_id": "VARCHAR(200) NOT NULL DEFAULT ''",
    },
}


# Indexes added after the first release. CREATE INDEX IF NOT EXISTS is
# idempotent, so it is safe to run on every startup.
_MISSING_INDEXES: tuple[tuple[str, str], ...] = (
    ("ix_interview_sessions_compatibility_id", "interview_sessions (compatibility_id)"),
    ("ix_pipeline_entries_job_posting_id", "pipeline_entries (job_posting_id)"),
    ("ix_compatibility_reports_resume_id", "compatibility_reports (resume_id)"),
    ("ix_compatibility_reports_job_id", "compatibility_reports (job_id)"),
    ("ix_interview_messages_session_id", "interview_messages (session_id)"),
    ("ix_interview_evaluations_session_id", "interview_evaluations (session_id)"),
    ("ix_learning_tasks_report_id", "learning_tasks (report_id)"),
    ("ix_skill_gap_reports_compatibility_id", "skill_gap_reports (compatibility_id)"),
    ("ix_job_postings_user_source", "job_postings (user_id, source)"),
    ("ix_job_postings_user_posted", "job_postings (user_id, posted_at)"),
    ("ix_job_postings_user_dedupe", "job_postings (user_id, dedupe_key)"),
    ("ix_job_postings_user_remote", "job_postings (user_id, remote)"),
    ("ix_cli_sync_runs_user", "cli_sync_runs (user_id, id)"),
)


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

    if settings.database_url.startswith("sqlite"):
        for index_name, index_body in _MISSING_INDEXES:
            table = index_body.split(" ")[0]
            if table not in existing_tables:
                continue
            try:
                with engine.begin() as conn:
                    conn.execute(text(f"CREATE INDEX IF NOT EXISTS {index_name} ON {index_body}"))
            except Exception:  # pragma: no cover
                continue


def ensure_default_user(db) -> User:
    user = db.query(User).first()
    if not user:
        user = User(email="candidate@local", display_name="Candidate")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user
