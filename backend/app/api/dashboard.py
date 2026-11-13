"""Dashboard and analytics aggregates."""
from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database.models import (
    CompatibilityReport,
    InterviewSession,
    JobAnalysis,
    LearningTask,
    ResumeProfile,
    SkillGapReport,
    UsageLog,
    get_db,
    User,

)
from .deps import get_current_user, iso, require_auth

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    resumes = db.query(ResumeProfile).filter(ResumeProfile.user_id == user.id).order_by(ResumeProfile.created_at.desc()).all()
    latest_resume = resumes[0] if resumes else None
    jobs = db.query(JobAnalysis).filter(JobAnalysis.user_id == user.id).order_by(JobAnalysis.created_at.desc(), JobAnalysis.id.desc()).limit(6).all()
    reports = (
        db.query(CompatibilityReport)
        .filter(CompatibilityReport.user_id == user.id)
        .order_by(CompatibilityReport.created_at.desc(), CompatibilityReport.id.desc())
        .all()
    )
    latest_report = reports[0] if reports else None
    avg_score = round(sum(r.overall_score for r in reports) / len(reports), 1) if reports else 0.0
    gap = (
        db.query(SkillGapReport)
        .filter(SkillGapReport.user_id == user.id)
        .filter_by(compatibility_id=latest_report.id)
        .order_by(SkillGapReport.id.desc())
        .first()
        if latest_report
        else db.query(SkillGapReport).filter(SkillGapReport.user_id == user.id).order_by(SkillGapReport.id.desc()).first()
    )
    tasks = gap.tasks if gap else []
    completed_tasks = sum(1 for t in tasks if t.completed)
    sessions = (
        db.query(InterviewSession)
        .filter(InterviewSession.user_id == user.id)
        .order_by(InterviewSession.created_at.desc(), InterviewSession.id.desc())
        .all()
    )
    completed_sessions = [s for s in sessions if s.status == "completed"]
    avg_interview = (
        round(
            sum((s.report or {}).get("overall_performance", 0) for s in completed_sessions)
            / len(completed_sessions),
            1,
        )
        if completed_sessions
        else 0.0
    )

    profile = (latest_resume.profile if latest_resume else {}) or {}
    recent_activity = (
        db.query(UsageLog).order_by(UsageLog.created_at.desc(), UsageLog.id.desc()).limit(8).all()
    )

    return {
        "candidate": {
            "name": profile.get("name", "Candidate"),
            "headline": profile.get("headline", ""),
            "email": profile.get("email", ""),
            "skills": profile.get("skills", []),
            "skill_count": len(profile.get("skills", [])),
            "project_count": len(profile.get("projects", [])),
            "experience_years": profile.get("years_experience", 0),
            "resume_id": latest_resume.id if latest_resume else None,
            "resume_filename": latest_resume.filename if latest_resume else "",
            "provider": latest_resume.provider if latest_resume else "",
            "weaknesses": profile.get("resume_weaknesses", [])[:3],
            "uploaded_at": iso(latest_resume.created_at) if latest_resume else None,
        },
        "stats": {
            "resume_count": len(resumes),
            "job_count": db.query(JobAnalysis).filter(JobAnalysis.user_id == user.id).count(),
            "analysis_count": len(reports),
            "average_compatibility": avg_score,
            "latest_compatibility": latest_report.overall_score if latest_report else 0,
            "interview_count": len(sessions),
            "average_interview": avg_interview,
            "preparation_percent": round(completed_tasks / len(tasks) * 100, 1) if tasks else 0.0,
            "tasks_completed": completed_tasks,
            "tasks_total": len(tasks),
        },
        "latest_analysis": (
            {
                "id": latest_report.id,
                "score": latest_report.overall_score,
                "verdict": (latest_report.report or {}).get("verdict", ""),
                "job_title": (
                    db.get(JobAnalysis, latest_report.job_id).title if db.get(JobAnalysis, latest_report.job_id) else ""
                ),
                "created_at": iso(latest_report.created_at),
                "matched": len((latest_report.report or {}).get("matched_skills", [])),
                "missing": len((latest_report.report or {}).get("missing_skills", [])),
            }
            if latest_report
            else None
        ),
        "recent_jobs": [
            {
                "id": j.id,
                "title": j.title,
                "company": j.company,
                "created_at": iso(j.created_at),
                "required_skills": (j.profile or {}).get("required_skills", [])[:6],
            }
            for j in jobs
        ],
        "compatibility_history": [
            {
                "id": r.id,
                "score": r.overall_score,
                "created_at": iso(r.created_at),
                "job_title": (
                    db.get(JobAnalysis, r.job_id).title if db.get(JobAnalysis, r.job_id) else ""
                ),
            }
            for r in reports[:10][::-1]
        ],
        "interview_history": [
            {
                "id": s.id,
                "role": s.role,
                "score": (s.report or {}).get("overall_performance", 0),
                "status": s.status,
                "created_at": iso(s.created_at),
            }
            for s in completed_sessions[:10][::-1]
        ],
        "skill_gap": (
            {
                "id": gap.id,
                "priority_skills": (gap.report or {}).get("priority_skills", [])[:6],
                "total_estimated_hours": (gap.report or {}).get("total_estimated_hours", 0),
                "progress_percent": round(completed_tasks / len(tasks) * 100, 1) if tasks else 0.0,
                "tasks": [
                    {
                        "id": t.id,
                        "title": t.title,
                        "skill": t.skill,
                        "completed": t.completed,
                        "estimated_hours": t.estimated_hours,
                    }
                    for t in tasks[:6]
                ],
            }
            if gap
            else None
        ),
        "recent_activity": [
            {
                "provider": a.provider,
                "model": a.model,
                "agent": a.agent,
                "status": a.status,
                "latency_ms": a.latency_ms,
                "created_at": iso(a.created_at),
            }
            for a in recent_activity
        ],
    }


@router.get("/analytics")
def analytics(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    reports = (
        db.query(CompatibilityReport)
        .filter(CompatibilityReport.user_id == user.id)
        .order_by(CompatibilityReport.created_at.asc(), CompatibilityReport.id.asc())
        .all()
    )
    sessions = (
        db.query(InterviewSession)
        .filter(InterviewSession.user_id == user.id)
        .filter(InterviewSession.status == "completed")
        .order_by(InterviewSession.created_at.asc())
        .all()
    )
    gap_records = db.query(SkillGapReport).filter(SkillGapReport.user_id == user.id).order_by(SkillGapReport.id.desc()).all()
    tasks = db.query(LearningTask).all()

    preparation_by_skill = []
    for record in gap_records[:12]:
        record_tasks = db.query(LearningTask).filter_by(report_id=record.id).all()
        priorities = (record.report or {}).get("priority_skills", [])
        preparation_by_skill.append(
            {
                "gap_id": record.id,
                "skill": priorities[0] if priorities else "",
                "completed": sum(1 for t in record_tasks if t.completed),
                "total": len(record_tasks),
                "percent": round(
                    sum(1 for t in record_tasks if t.completed) / len(record_tasks) * 100, 1
                )
                if record_tasks
                else 0.0,
            }
        )

    missing_counter: Counter[str] = Counter()
    partial_counter: Counter[str] = Counter()
    category_totals: dict[str, list[float]] = {}
    for report in reports:
        data = report.report or {}
        for item in data.get("missing_skills", []):
            missing_counter[item.get("skill", "")] += 1
        for item in data.get("partially_matched_skills", []):
            partial_counter[item.get("skill", "")] += 1
        for category in data.get("category_scores", []):
            category_totals.setdefault(category.get("name", ""), []).append(category.get("score", 0))

    return {
        "compatibility_history": [
            {
                "id": r.id,
                "score": r.overall_score,
                "created_at": iso(r.created_at),
                "job_title": (
                    db.get(JobAnalysis, r.job_id).title if db.get(JobAnalysis, r.job_id) else ""
                ),
            }
            for r in reports[-20:]
        ],
        "interview_history": [
            {
                "id": s.id,
                "role": s.role,
                "score": (s.report or {}).get("overall_performance", 0),
                "readiness": (s.report or {}).get("readiness", ""),
                "created_at": iso(s.created_at),
            }
            for s in sessions[-20:]
        ],
        "weak_skills": [
            {"skill": skill, "missing": count, "partial": partial_counter.get(skill, 0)}
            for skill, count in missing_counter.most_common(12)
            if skill
        ],
        "partial_skills": [
            {"skill": skill, "count": count} for skill, count in partial_counter.most_common(10)
        ],
        "category_averages": [
            {
                "name": name,
                "average": round(sum(values) / len(values), 1),
                "samples": len(values),
            }
            for name, values in category_totals.items()
        ],
        "preparation": {
            "total_tasks": len(tasks),
            "completed_tasks": sum(1 for t in tasks if t.completed),
            "hours_planned": round(sum(t.estimated_hours for t in tasks), 1),
            "hours_completed": round(sum(t.estimated_hours for t in tasks if t.completed), 1),
            "by_skill": preparation_by_skill,
            "gap_reports": len(gap_records),
        },
        "totals": {
            "analyses": len(reports),
            "interviews": len(sessions),
            "average_compatibility": round(sum(r.overall_score for r in reports) / len(reports), 1) if reports else 0,
            "average_interview": round(
                sum((s.report or {}).get("overall_performance", 0) for s in sessions) / len(sessions), 1
            )
            if sessions
            else 0,
        },
    }
