"""Resume upload and profile endpoints."""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..config import settings
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
from ..schemas import CandidateProfile
from ..services.resume_parser import ResumeParseError
from .deps import get_gateway, iso, require_auth

router = APIRouter(prefix="/api/resume", tags=["resume"], dependencies=[Depends(require_auth)])

ALLOWED_EXTENSIONS = {"pdf", "txt", "md", "docx"}


def resume_to_dict(resume: ResumeProfile, include_text: bool = False) -> dict:
    data = {
        "id": resume.id,
        "filename": resume.filename,
        "provider": resume.provider,
        "profile": resume.profile,
        "created_at": iso(resume.created_at),
        "updated_at": iso(resume.updated_at),
    }
    if include_text:
        data["raw_text"] = resume.raw_text
    return data


@router.post("/upload")
async def upload_resume(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    gateway: GatewayManager = Depends(get_gateway),
):
    filename = file.filename or "resume.pdf"
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, "Unsupported file type. Upload a PDF, DOCX, TXT or MD file.")
    max_bytes = settings.max_upload_mb * 1024 * 1024
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(413, f"File exceeds the {settings.max_upload_mb} MB limit.")
    if len(data) < 40:
        raise HTTPException(400, "The uploaded file is empty.")

    from ..agents.resume_agent import ResumeAgent
    from ..services.resume_parser import clean_text, extract_text

    try:
        # Extract once before writing the file so bad uploads leave no trace.
        raw_text = clean_text(extract_text(filename, data))
        profile, provider, warning = await ResumeAgent(gateway).analyze_text(raw_text)
    except ResumeParseError as exc:
        raise HTTPException(422, str(exc)) from exc

    user = ensure_default_user(db)
    stored_name = f"{uuid.uuid4().hex}_{Path(filename).name}"[:200]
    path = settings.upload_path / stored_name
    path.write_bytes(data)
    try:
        path.chmod(0o600)
    except OSError:
        pass

    record = ResumeProfile(
        user_id=user.id,
        filename=filename[:255],
        storage_path=str(path),
        raw_text=raw_text,
        profile=profile.model_dump(),
        provider=provider,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {**resume_to_dict(record), "warning": warning}


@router.get("/profile")
def get_profile(db: Session = Depends(get_db)):
    resume = (
        db.query(ResumeProfile)
        .order_by(ResumeProfile.created_at.desc(), ResumeProfile.id.desc())
        .first()
    )
    if not resume:
        raise HTTPException(404, "No resume uploaded yet.")
    return resume_to_dict(resume)


@router.get("/profile/{resume_id}")
def get_profile_by_id(resume_id: int, db: Session = Depends(get_db)):
    resume = db.get(ResumeProfile, resume_id)
    if not resume:
        raise HTTPException(404, "Resume not found.")
    return resume_to_dict(resume)


@router.get("")
def list_resumes(db: Session = Depends(get_db)):
    rows = db.query(ResumeProfile).order_by(ResumeProfile.created_at.desc()).all()
    return [
        {
            "id": r.id,
            "filename": r.filename,
            "provider": r.provider,
            "name": (r.profile or {}).get("name", ""),
            "skills": (r.profile or {}).get("skills", []),
            "created_at": iso(r.created_at),
        }
        for r in rows
    ]


@router.delete("/{resume_id}")
def delete_resume(resume_id: int, db: Session = Depends(get_db)):
    resume = db.get(ResumeProfile, resume_id)
    if not resume:
        raise HTTPException(404, "Resume not found.")
    try:
        Path(resume.storage_path).unlink(missing_ok=True)
    except OSError:
        pass
    report_ids = [
        r.id for r in db.query(CompatibilityReport).filter_by(resume_id=resume_id).all()
    ]
    if report_ids:
        gap_ids = [
            g.id for g in db.query(SkillGapReport).filter(SkillGapReport.compatibility_id.in_(report_ids)).all()
        ]
        if gap_ids:
            db.query(LearningTask).filter(LearningTask.report_id.in_(gap_ids)).delete(synchronize_session=False)
            db.query(SkillGapReport).filter(SkillGapReport.id.in_(gap_ids)).delete(synchronize_session=False)
        db.query(CompatibilityReport).filter(CompatibilityReport.id.in_(report_ids)).delete(synchronize_session=False)
    db.delete(resume)
    db.commit()
    return {"deleted": True, "id": resume_id}
