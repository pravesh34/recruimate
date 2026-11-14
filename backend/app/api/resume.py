"""Resume upload and profile endpoints."""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from ..config import settings
from ..database.models import (
    CompatibilityReport,
    JobAnalysis,
    LearningTask,
    ResumeProfile,
    SkillGapReport,
    User,
    get_db,
)
from ..gateway import GatewayManager
from ..schemas import CandidateProfile
from ..services.resume_parser import ResumeParseError
from .deps import get_current_user, get_gateway, iso

router = APIRouter(prefix="/api/resume", tags=["resume"])

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


def _write_canonical_pdf(user_id: int, original_path: Path, raw_text: str, filename: str) -> Path | None:
    """Render the resume text to a PDF next to the original upload.

    Returns the PDF path, or ``None`` when PDF rendering is unavailable
    (the original upload is still kept and served).
    """
    try:
        from ..services.resume_pdf import render_resume_pdf

        pdf_bytes = render_resume_pdf(raw_text, title=Path(filename).stem or "Resume")
    except Exception:  # pragma: no cover - reportlab missing or bad input
        return None
    pdf_path = settings.upload_path / f"{original_path.stem}.pdf"
    try:
        pdf_path.write_bytes(pdf_bytes)
        pdf_path.chmod(0o600)
    except OSError:
        return None
    return pdf_path


@router.post("/upload")
async def upload_resume(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    gateway: GatewayManager = Depends(get_gateway),
    user: User = Depends(get_current_user),
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

    # Verify the file signature (magic bytes) matches the extension: a text
    # payload renamed to .pdf — or worse, an executable/script — is rejected
    # before it ever reaches the parser or disk.
    head = data[:8]
    if suffix == "pdf" and not head.startswith(b"%PDF"):
        raise HTTPException(400, "That file is not a valid PDF (file content does not match the extension).")
    if suffix == "docx" and not head.startswith(b"PK\x03\x04"):
        raise HTTPException(400, "That file is not a valid DOCX (file content does not match the extension).")

    from ..agents.resume_agent import ResumeAgent
    from ..services.resume_parser import clean_text, extract_text

    try:
        # Extract once before writing the file so bad uploads leave no trace.
        raw_text = clean_text(extract_text(filename, data))
        profile, provider, warning = await ResumeAgent(gateway).analyze_text(raw_text)
    except ResumeParseError as exc:
        raise HTTPException(422, str(exc)) from exc

    user_id = user.id  # the authenticated caller owns this upload
    stored_name = f"{uuid.uuid4().hex}_{Path(filename).name}"[:200]
    path = settings.upload_path / stored_name
    path.write_bytes(data)
    try:
        path.chmod(0o600)
    except OSError:
        pass

    # Canonical PDF version: every resume is stored as PDF so the candidate
    # always has one consistent, ATS-friendly document (even if they
    # uploaded TXT/DOCX/Markdown).
    pdf_path = _write_canonical_pdf(user.id, path, raw_text, filename)

    record = ResumeProfile(
        user_id=user_id,
        filename=filename[:255],
        storage_path=str(path),
        pdf_path=str(pdf_path) if pdf_path else "",
        raw_text=raw_text,
        profile=profile.model_dump(),
        provider=provider,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {**resume_to_dict(record), "warning": warning}


@router.get("/profile")
def get_profile(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    resume = (
        db.query(ResumeProfile)
        .filter(ResumeProfile.user_id == user.id)
        .order_by(ResumeProfile.created_at.desc(), ResumeProfile.id.desc())
        .first()
    )
    if not resume:
        raise HTTPException(404, "No resume uploaded yet.")
    return resume_to_dict(resume)


@router.get("/profile/{resume_id}")
def get_profile_by_id(resume_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    resume = db.get(ResumeProfile, resume_id)
    if resume and resume.user_id != user.id:
        raise HTTPException(404, "Resume not found.")
    if not resume:
        raise HTTPException(404, "Resume not found.")
    return resume_to_dict(resume)


_CONTENT_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "txt": "text/plain; charset=utf-8",
    "md": "text/markdown; charset=utf-8",
}


@router.get("/{resume_id}/download")
def download_resume(
    resume_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    """Serve the original uploaded file to its owner only.

    The stored name is a UUID-prefixed name written at upload time, so it is
    safe to build a path from; the extension lookup drives the content type.
    Foreign resumes are reported as 404, never as 403, so ids cannot be
    probed.
    """
    resume = db.get(ResumeProfile, resume_id)
    if not resume or resume.user_id != user.id:
        raise HTTPException(404, "Resume not found.")

    # Prefer the canonical PDF rendering.
    pdf_path = Path(resume.pdf_path or "")
    if pdf_path.is_file():
        return FileResponse(
            pdf_path,
            media_type="application/pdf",
            filename=Path(resume.filename or "resume").stem + ".pdf",
            content_disposition_type="inline",
        )

    path = Path(resume.storage_path)
    if path.is_file():
        suffix = path.suffix.lstrip(".").lower()
        media_type = _CONTENT_TYPES.get(suffix, "application/octet-stream")
        download_name = Path(resume.filename or "resume").name
        return FileResponse(
            path,
            media_type=media_type,
            filename=download_name,
            content_disposition_type="inline",
        )
    # Seeded/demo profiles and pruned storage have no original file on disk.
    # Serve the stored resume text instead so "open my resume" never dead-ends.
    if (resume.raw_text or "").strip():
        return Response(
            content=resume.raw_text,
            media_type="text/plain; charset=utf-8",
            headers={
                "Content-Disposition": 'inline; filename="resume.txt"',
            },
        )
    raise HTTPException(404, "The original file is no longer stored on this device.")


@router.get("")
def list_resumes(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (
        db.query(ResumeProfile)
        .filter(ResumeProfile.user_id == user.id)
        .order_by(ResumeProfile.created_at.desc())
        .all()
    )
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
def delete_resume(resume_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    resume = db.get(ResumeProfile, resume_id)
    if resume and resume.user_id != user.id:
        raise HTTPException(404, "Resume not found.")
    if not resume:
        raise HTTPException(404, "Resume not found.")
    try:
        Path(resume.storage_path).unlink(missing_ok=True)
    except OSError:
        pass
    if resume.pdf_path:
        try:
            Path(resume.pdf_path).unlink(missing_ok=True)
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
