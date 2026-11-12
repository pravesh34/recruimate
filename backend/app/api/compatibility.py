"""Compatibility analysis, full supervisor run and report retrieval."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..agents.compatibility_agent import CompatibilityAgent
from ..agents.job_agent import JobAgent
from ..database.models import (
    CompatibilityReport,
    JobAnalysis,
    LearningTask,
    ResumeProfile,
    SkillGapReport,
    ensure_default_user,
    get_db,
)
from ..gateway import GatewayManager
from ..graph.workflow import SupervisorAgent
from ..schemas import CandidateProfile, JobProfile
from ..services.roadmap_service import generate_roadmap
from .deps import get_gateway, iso, require_auth
from .schemas import AnalysisRunRequest, CompatibilityAnalyzeRequest

router = APIRouter(prefix="/api", tags=["compatibility"], dependencies=[Depends(require_auth)])


def persist_gap(db: Session, user_id: int, compatibility_id: int, gap) -> SkillGapReport:
    record = SkillGapReport(
        user_id=user_id,
        compatibility_id=compatibility_id,
        report=gap.model_dump(),
    )
    db.add(record)
    db.flush()
    for step in gap.learning_roadmap:
        db.add(
            LearningTask(
                report_id=record.id,
                skill=step.skill[:120],
                title=step.title[:255],
                description=(
                    step.description
                    + "\nTopics: "
                    + "; ".join(step.study_topics)
                    + ("\nPractice: " + step.practice_project if step.practice_project else "")
                )[:4000],
                estimated_hours=step.estimated_hours,
            )
        )
    db.commit()
    db.refresh(record)
    return record


def gap_to_dict(record: SkillGapReport) -> dict:
    tasks = [
        {
            "id": t.id,
            "skill": t.skill,
            "title": t.title,
            "description": t.description,
            "estimated_hours": t.estimated_hours,
            "completed": t.completed,
        }
        for t in sorted(record.tasks, key=lambda t: t.id)
    ]
    done = sum(1 for t in tasks if t["completed"])
    return {
        "id": record.id,
        "compatibility_id": record.compatibility_id,
        "report": record.report,
        "tasks": tasks,
        "progress": {
            "completed": done,
            "total": len(tasks),
            "percent": round(done / len(tasks) * 100, 1) if tasks else 0.0,
        },
        "created_at": iso(record.created_at),
    }


def compatibility_to_dict(record: CompatibilityReport, db: Session) -> dict:
    job = db.get(JobAnalysis, record.job_id)
    resume = db.get(ResumeProfile, record.resume_id)
    gap = (
        db.query(SkillGapReport)
        .filter_by(compatibility_id=record.id)
        .order_by(SkillGapReport.id.desc())
        .first()
    )
    return {
        "id": record.id,
        "overall_score": record.overall_score,
        "report": record.report,
        "resume_id": record.resume_id,
        "job_id": record.job_id,
        "resume_name": ((resume.profile or {}).get("name") if resume else "") or "",
        "job_title": job.title if job else "",
        "company": job.company if job else "",
        "gap_id": gap.id if gap else None,
        "created_at": iso(record.created_at),
    }


async def _resolve_job(
    db: Session, gateway: GatewayManager, job_id: int | None, description: str
) -> JobAnalysis:
    if job_id:
        job = db.get(JobAnalysis, job_id)
        if not job:
            raise HTTPException(404, "Job analysis not found.")
        return job
    if description.strip():
        profile, provider, warning = await JobAgent(gateway).analyze(description.strip()[:40000])
        user = ensure_default_user(db)
        job = JobAnalysis(
            user_id=user.id,
            title=profile.job_title[:255],
            company=profile.company[:255],
            raw_text=description.strip()[:40000],
            profile=profile.model_dump(),
            provider=provider,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job
    latest = db.query(JobAnalysis).order_by(JobAnalysis.created_at.desc(), JobAnalysis.id.desc()).first()
    if latest:
        return latest
    raise HTTPException(400, "Analyse a job description first or provide one.")


def _resolve_resume(db: Session, resume_id: int | None) -> ResumeProfile:
    resume = (
        db.get(ResumeProfile, resume_id)
        if resume_id
        else db.query(ResumeProfile).order_by(ResumeProfile.created_at.desc(), ResumeProfile.id.desc()).first()
    )
    if not resume:
        raise HTTPException(404, "Upload a resume first.")
    return resume


@router.post("/compatibility/analyze")
async def analyze_compatibility(
    payload: CompatibilityAnalyzeRequest,
    db: Session = Depends(get_db),
    gateway: GatewayManager = Depends(get_gateway),
):
    resume = _resolve_resume(db, payload.resume_id)
    job = await _resolve_job(db, gateway, payload.job_id, payload.job_description)
    candidate = CandidateProfile.model_validate(resume.profile or {})
    job_profile = JobProfile.model_validate(job.profile or {})
    report = CompatibilityAgent().analyze(candidate, job_profile, resume.raw_text or "")

    user = ensure_default_user(db)
    record = CompatibilityReport(
        user_id=user.id,
        resume_id=resume.id,
        job_id=job.id,
        overall_score=report.overall_score,
        report=report.model_dump(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    gap_payload = None
    if payload.run_gap_analysis:
        gap = generate_roadmap(report)
        gap_record = persist_gap(db, user.id, record.id, gap)
        gap_payload = gap_to_dict(gap_record)

    return {
        **compatibility_to_dict(record, db),
        "gap": gap_payload,
        "question_count": 0,
        "warning": "",
    }


@router.post("/analysis/run")
async def run_full_analysis(
    payload: AnalysisRunRequest,
    db: Session = Depends(get_db),
    gateway: GatewayManager = Depends(get_gateway),
):
    """Run the full LangGraph supervisor: resume → job → compatibility → gaps → interview prep."""
    resume = _resolve_resume(db, payload.resume_id)
    job = await _resolve_job(db, gateway, payload.job_id, payload.job_description)
    supervisor = SupervisorAgent(gateway)
    state = await supervisor.run(resume.raw_text or "", job.raw_text or "")
    if not state.get("candidate") or not state.get("compatibility") or not state.get("gaps"):
        raise HTTPException(500, "The analysis workflow did not complete. Check provider settings and try again.")

    user = ensure_default_user(db)
    # Refresh the stored profiles with the supervisor output (keeps them consistent).
    resume.profile = state["candidate"].model_dump()
    resume.provider = state.get("providers", {}).get("resume_agent", resume.provider)
    job.profile = state["job"].model_dump()
    job.title = state["job"].job_title[:255]
    job.company = state["job"].company[:255]
    job.provider = state.get("providers", {}).get("job_agent", job.provider)
    db.commit()

    compat = state["compatibility"]
    record = CompatibilityReport(
        user_id=user.id,
        resume_id=resume.id,
        job_id=job.id,
        overall_score=compat.overall_score,
        report=compat.model_dump(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    gap_record = persist_gap(db, user.id, record.id, state["gaps"])

    return {
        **compatibility_to_dict(record, db),
        "gap": gap_to_dict(gap_record),
        "candidate": state["candidate"].model_dump(),
        "job": state["job"].model_dump(),
        "questions": state["questions"].model_dump() if state.get("questions") else {"questions": []},
        "activity": state.get("activity", []),
        "providers": state.get("providers", {}),
        "errors": state.get("errors", []),
        "engine": supervisor.engine,
    }


@router.get("/compatibility")
def list_compatibility(db: Session = Depends(get_db)):
    rows = (
        db.query(CompatibilityReport)
        .order_by(CompatibilityReport.created_at.desc(), CompatibilityReport.id.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "id": r.id,
            "overall_score": r.overall_score,
            "verdict": (r.report or {}).get("verdict", ""),
            "resume_id": r.resume_id,
            "job_id": r.job_id,
            "job_title": (db.get(JobAnalysis, r.job_id).title if db.get(JobAnalysis, r.job_id) else ""),
            "created_at": iso(r.created_at),
        }
        for r in rows
    ]


@router.get("/compatibility/{report_id}")
def get_compatibility(report_id: int, db: Session = Depends(get_db)):
    record = db.get(CompatibilityReport, report_id)
    if not record:
        raise HTTPException(404, "Compatibility report not found.")
    return compatibility_to_dict(record, db)
