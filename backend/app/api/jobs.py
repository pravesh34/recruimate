"""Job description analysis endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..agents.job_agent import JobAgent
from ..database.models import JobAnalysis, ensure_default_user, get_db
from ..gateway import GatewayManager
from ..utils.web import UnsafeURLError, fetch_job_posting
from .deps import get_gateway, iso, require_auth
from .schemas import JobAnalyzeRequest

router = APIRouter(prefix="/api/jobs", tags=["jobs"], dependencies=[Depends(require_auth)])


def job_to_dict(job: JobAnalysis, include_text: bool = False) -> dict:
    data = {
        "id": job.id,
        "title": job.title,
        "company": job.company,
        "source_url": job.source_url,
        "profile": job.profile,
        "provider": job.provider,
        "created_at": iso(job.created_at),
    }
    if include_text:
        data["raw_text"] = job.raw_text
    return data


@router.post("/analyze")
async def analyze_job(
    payload: JobAnalyzeRequest,
    db: Session = Depends(get_db),
    gateway: GatewayManager = Depends(get_gateway),
):
    text = (payload.description or "").strip()
    source_url = (payload.url or "").strip()
    warning = ""
    if not text and source_url:
        try:
            text = await fetch_job_posting(source_url)
        except UnsafeURLError as exc:
            raise HTTPException(400, f"Unsafe or invalid URL: {exc}") from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except Exception as exc:
            raise HTTPException(422, f"Could not fetch that job posting: {exc}") from exc
    if len(text) < 40:
        raise HTTPException(400, "Paste a job description (at least 40 characters) or a public posting URL.")
    if len(text) > 40000:
        text = text[:40000]
        warning = "Description was truncated to 40,000 characters."

    profile, provider, agent_warning = await JobAgent(gateway).analyze(text)
    if agent_warning:
        warning = (warning + " " + agent_warning).strip()

    user = ensure_default_user(db)
    job = JobAnalysis(
        user_id=user.id,
        title=(payload.title or profile.job_title)[:255],
        company=profile.company[:255],
        source_url=source_url[:1024],
        raw_text=text,
        profile=profile.model_dump(),
        provider=provider,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return {**job_to_dict(job), "warning": warning}


@router.get("")
def list_jobs(db: Session = Depends(get_db)):
    rows = db.query(JobAnalysis).order_by(JobAnalysis.created_at.desc()).all()
    return [
        {
            "id": j.id,
            "title": j.title,
            "company": j.company,
            "role_category": (j.profile or {}).get("role_category", "general"),
            "required_skills": (j.profile or {}).get("required_skills", []),
            "created_at": iso(j.created_at),
        }
        for j in rows
    ]


@router.get("/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(JobAnalysis, job_id)
    if not job:
        raise HTTPException(404, "Job analysis not found.")
    return job_to_dict(job, include_text=True)


@router.delete("/{job_id}")
def delete_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(JobAnalysis, job_id)
    if not job:
        raise HTTPException(404, "Job analysis not found.")
    db.delete(job)
    db.commit()
    return {"deleted": True, "id": job_id}
