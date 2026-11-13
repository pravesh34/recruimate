"""Skill-gap roadmap endpoints and learning task tracking."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database.models import (
    CompatibilityReport,
    LearningTask,
    SkillGapReport,
    get_db,
)
from ..schemas import CompatibilityReport as CompatibilitySchema
from ..services.roadmap_service import generate_roadmap
from .compatibility import gap_to_dict, persist_gap
from .deps import get_current_user, iso
from .schemas import GapForJobRequest, GapGenerateRequest, TaskUpdateRequest

router = APIRouter(prefix="/api/skill-gaps", tags=["skill gaps"])


@router.post("/generate")
def generate_gap(
    payload: GapGenerateRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    compatibility = db.get(CompatibilityReport, payload.compatibility_id)
    if not compatibility or compatibility.user_id != user.id:
        raise HTTPException(404, "Compatibility report not found.")
    report = CompatibilitySchema.model_validate(compatibility.report or {})
    gap = generate_roadmap(report)
    record = persist_gap(db, user.id, compatibility.id, gap)
    return gap_to_dict(record)


@router.get("")
def list_gaps(db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = (
        db.query(SkillGapReport)
        .filter(SkillGapReport.user_id == user.id)
        .order_by(SkillGapReport.created_at.desc(), SkillGapReport.id.desc())
        .limit(30)
        .all()
    )
    return [
        {
            "id": r.id,
            "compatibility_id": r.compatibility_id,
            "summary": (r.report or {}).get("summary", ""),
            "priority_skills": (r.report or {}).get("priority_skills", []),
            "total_estimated_hours": (r.report or {}).get("total_estimated_hours", 0),
            "created_at": iso(r.created_at),
        }
        for r in rows
    ]


@router.patch("/tasks/{task_id}")
def update_task(
    task_id: int,
    payload: TaskUpdateRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    task = db.get(LearningTask, task_id)
    if not task or task.report is None or task.report.user_id != user.id:
        raise HTTPException(404, "Learning task not found.")
    task.completed = payload.completed
    db.commit()
    report = db.get(SkillGapReport, task.report_id)
    return gap_to_dict(report)


@router.get("/{gap_id}")
def get_gap(gap_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    record = db.get(SkillGapReport, gap_id)
    if not record or record.user_id != user.id:
        raise HTTPException(404, "Skill gap report not found.")
    return gap_to_dict(record)


@router.post("/generate-for-job")
def generate_gap_for_job(
    payload: GapForJobRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Build a plan of approach (roadmap) against a target-pool posting.

    The posting is mirrored into ``job_analyses`` so the resulting
    compatibility report and roadmap appear in history and analytics like any
    other analysis. Only the caller's pool jobs (or shared/demo postings) can
    be used.
    """
    from ..agents.compatibility_agent import CompatibilityAgent
    from ..database.models import JobAnalysis, JobPosting, ResumeProfile
    from ..schemas import CandidateProfile
    from ..services.posting_profile import build_job_profile

    posting = db.get(JobPosting, payload.job_id)
    if not posting or (posting.user_id is not None and posting.user_id != user.id):
        raise HTTPException(404, "Pool job not found.")

    resume = (
        db.query(ResumeProfile)
        .filter(ResumeProfile.user_id == user.id)
        .filter(ResumeProfile.id == payload.resume_id)
        .first()
        if payload.resume_id
        else db.query(ResumeProfile)
        .filter(ResumeProfile.user_id == user.id)
        .order_by(ResumeProfile.created_at.desc(), ResumeProfile.id.desc())
        .first()
    )
    if not resume:
        raise HTTPException(404, "Upload a resume first.")

    raw_profile = resume.profile or "{}"
    profile_dict = json.loads(raw_profile) if isinstance(raw_profile, str) else (raw_profile or {})
    try:
        candidate = CandidateProfile.model_validate(profile_dict)
    except Exception as exc:
        raise HTTPException(400, f"Resume profile could not be parsed: {exc}") from exc

    try:
        job_profile = build_job_profile(posting)
    except Exception as exc:
        raise HTTPException(422, f"That posting could not be parsed: {exc}") from exc

    report = CompatibilityAgent().analyze(candidate, job_profile, resume.raw_text or "")

    # Mirror the posting into job_analyses for history/analytics consistency.
    job = JobAnalysis(
        user_id=user.id,
        title=posting.title or job_profile.job_title,
        company=posting.company or job_profile.company,
        source_url=posting.url or "",
        raw_text=(posting.raw_text or "")[:40000],
        profile=job_profile.model_dump(),
        provider="pool",
    )
    db.add(job)
    db.flush()

    record = CompatibilityReport(
        user_id=user.id,
        resume_id=resume.id,
        job_id=job.id,
        overall_score=report.overall_score,
        report=report.model_dump(),
    )
    db.add(record)
    db.flush()

    gap = generate_roadmap(report)
    record_gap = persist_gap(db, user.id, record.id, gap)
    return {
        **gap_to_dict(record_gap),
        "compatibility_id": record.id,
        "compatibility_score": report.overall_score,
        "job": {
            "title": posting.title,
            "company": posting.company,
            "url": posting.url,
        },
    }
