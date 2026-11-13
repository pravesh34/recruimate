"""Account and data-deletion endpoints (privacy controls)."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..config import settings
from ..database.models import (
    CompatibilityReport,
    InterviewSession,
    JobAnalysis,
    LearningTask,
    ProviderConfiguration,
    ResumeProfile,
    SkillGapReport,
    UsageLog,
    get_db,
)
from .deps import iso, require_auth

router = APIRouter(prefix="/api/account", tags=["account"])


@router.get("")
def account_info(db: Session = Depends(get_db)):
    return {
        "mode": "trusted-local" if not settings.api_token else "token-protected",
        "storage": "SQLite on this device",
        "resume_count": db.query(ResumeProfile).count(),
        "job_count": db.query(JobAnalysis).count(),
        "interview_count": db.query(InterviewSession).count(),
        "provider_rows": db.query(ProviderConfiguration).count(),
    }


@router.delete("/data")
def delete_all_data(db: Session = Depends(get_db)):
    """Delete resumes, analyses, interviews, provider credentials and logs."""
    import datetime as dt

    for resume in db.query(ResumeProfile).all():
        try:
            Path(resume.storage_path).unlink(missing_ok=True)
        except OSError:
            pass
    for model in (
        InterviewSession,
        LearningTask,
        SkillGapReport,
        CompatibilityReport,
        JobAnalysis,
        ResumeProfile,
        ProviderConfiguration,
        UsageLog,
    ):
        db.query(model).delete(synchronize_session=False)
    db.commit()
    return {"deleted": True, "deleted_at": dt.datetime.now(dt.timezone.utc).isoformat()}
