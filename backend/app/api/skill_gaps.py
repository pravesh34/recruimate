"""Skill-gap roadmap endpoints and learning task tracking."""
from __future__ import annotations

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
from .schemas import GapGenerateRequest, TaskUpdateRequest

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
