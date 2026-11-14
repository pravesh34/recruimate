"""Account and data-deletion endpoints (privacy controls).

Every query is scoped to the authenticated caller: deletion removes only the
caller's rows, never another account's data. In trusted-local mode (auth
disabled) the caller is the single local candidate, matching the old MVP
behaviour.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..config import settings
from ..database.models import (
    AuthSession,
    CompatibilityReport,
    InterviewSession,
    JobAnalysis,
    JobPosting,
    LearningTask,
    PipelineEntry,
    ProviderConfiguration,
    ResumeProfile,
    SkillGapReport,
    UsageLog,
    get_db,
)
from .deps import get_current_user, iso

router = APIRouter(prefix="/api/account", tags=["account"])


@router.get("")
def account_info(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return {
        "mode": "trusted-local" if not settings.auth_enabled else "accounts",
        "storage": "SQLite on this device",
        "email": user.email,
        "resume_count": db.query(ResumeProfile).filter(ResumeProfile.user_id == user.id).count(),
        "job_count": db.query(JobAnalysis).filter(JobAnalysis.user_id == user.id).count(),
        "interview_count": db.query(InterviewSession)
        .filter(InterviewSession.user_id == user.id)
        .count(),
        "provider_rows": db.query(ProviderConfiguration)
        .filter(ProviderConfiguration.user_id == user.id)
        .count(),
    }


@router.delete("/data")
def delete_all_data(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Delete the caller's resumes, analyses, interviews, credentials and logs."""
    for resume in (
        db.query(ResumeProfile).filter(ResumeProfile.user_id == user.id).all()
    ):
        try:
            Path(resume.storage_path).unlink(missing_ok=True)
        except OSError:
            pass

    # ORM-level delete so messages/evaluations cascade along with sessions.
    for session_row in (
        db.query(InterviewSession).filter(InterviewSession.user_id == user.id).all()
    ):
        db.delete(session_row)

    # LearningTask links through SkillGapReport, so filter via a subquery.
    user_report_ids = db.query(SkillGapReport.id).filter(
        SkillGapReport.user_id == user.id
    )
    db.query(LearningTask).filter(
        LearningTask.report_id.in_(user_report_ids)
    ).delete(synchronize_session=False)

    for model in (
        SkillGapReport,
        CompatibilityReport,
        JobAnalysis,
        ResumeProfile,
        ProviderConfiguration,
        UsageLog,
    ):
        db.query(model).filter(model.user_id == user.id).delete(
            synchronize_session=False
        )
    # Pipeline entries, the caller's own pool postings and every refresh
    # session must go too, or deletion would leave orphaned rows and
    # refresh tokens that still resolve against a deleted account.
    db.query(PipelineEntry).filter(PipelineEntry.user_id == user.id).delete(
        synchronize_session=False
    )
    db.query(JobPosting).filter(JobPosting.user_id == user.id).delete(
        synchronize_session=False
    )
    db.query(AuthSession).filter(AuthSession.user_id == user.id).delete(
        synchronize_session=False
    )
    db.commit()
    return {"deleted": True, "deleted_at": dt.datetime.now(dt.timezone.utc).isoformat()}
