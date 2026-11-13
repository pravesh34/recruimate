"""Job description analysis endpoints."""
from __future__ import annotations

import json
import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..agents.job_agent import JobAgent
from ..database.models import JobAnalysis, User, ensure_default_user, get_db
from ..gateway import GatewayManager
from ..utils.web import UnsafeURLError, fetch_job_posting
from .deps import get_current_user, get_gateway, iso
from .schemas import JobAnalyzeRequest

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


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
    user: User = Depends(get_current_user),
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
def list_jobs(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (
        db.query(JobAnalysis)
        .filter(JobAnalysis.user_id == user.id)
        .order_by(JobAnalysis.created_at.desc())
        .all()
    )
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


@router.get("/match-resume")
async def match_resume_to_jobs(
    resume_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Search jobs according to resume and rank them by compatibility.

    Given a resume, computes a deterministic compatibility score between the
    resume and every stored job posting, then returns the jobs ranked by
    score (highest first) so the candidate can shortlist and apply.

    Args:
        resume_id: Resume profile id. Uses the most recent resume if omitted.

    Returns:
        ``{"matches": [...]}`` where each match carries the job identity,
        the compatibility score, and the full explainable report
        (matched / partial / missing skills, evidence, strengths, concerns).
    """
    from ..agents.compatibility_agent import CompatibilityAgent
    from ..database.models import ResumeProfile
    from ..schemas import CandidateProfile, JobProfile
    from ..services.skills import extract_skills

    resume = (
        db.query(ResumeProfile)
        .filter(ResumeProfile.user_id == user.id)
        .filter(ResumeProfile.id == resume_id)
        .first()
        if resume_id
        else db.query(ResumeProfile)
        .filter(ResumeProfile.user_id == user.id)
        .order_by(ResumeProfile.created_at.desc(), ResumeProfile.id.desc())
        .first()
    )
    if not resume:
        raise HTTPException(404, "Upload a resume first.")

    # The stored profile is JSON text, not a native JSON column.
    raw_profile = resume.profile or "{}"
    profile_dict = json.loads(raw_profile) if isinstance(raw_profile, str) else (raw_profile or {})
    try:
        candidate = CandidateProfile.model_validate(profile_dict)
    except Exception as exc:
        raise HTTPException(400, f"Resume profile could not be parsed: {exc}") from exc

    rows = db.execute(
        text(
            "SELECT id, title, company, location, url, raw_text, parsed "
            "FROM job_postings ORDER BY id"
        )
    ).fetchall()
    if not rows:
        return {"matches": [], "resume_id": resume.id, "message": "No job postings found."}

    agent = CompatibilityAgent()
    matches: list[dict] = []

    for job_id, title, company, location, url, raw_text, parsed_json in rows:
        parsed = json.loads(parsed_json) if isinstance(parsed_json, str) else (parsed_json or {})

        # Build a job profile from whatever the posting already carries.
        required = parsed.get("skills") or parsed.get("required_skills") or []
        preferred = parsed.get("preferred_skills") or []
        required = required if isinstance(required, list) else [required]
        preferred = preferred if isinstance(preferred, list) else [preferred]

        # Postings imported from job boards often have no parsed skills yet.
        # Recover them from the description so the ranking is meaningful.
        clean_text = re.sub(r"<[^>]+>", " ", raw_text or "")
        clean_text = re.sub(r"\s+", " ", clean_text).strip()

        if not required and clean_text:
            required = extract_skills(clean_text)

        # Pull a minimum-experience hint out of the description ("3+ years").
        min_years = parsed.get("min_years_experience")
        if not min_years and clean_text:
            match = re.search(r"(\d+)\s*\+?\s*years", clean_text, re.IGNORECASE)
            if match:
                try:
                    min_years = float(match.group(1))
                except ValueError:
                    min_years = 0.0

        def _as_list(value) -> list[str]:
            if not value:
                return []
            if isinstance(value, list):
                return [str(v) for v in value if v]
            return [str(value)]

        job_profile = JobProfile.model_validate(
            {
                "job_title": title or "Untitled role",
                "company": company or "Unknown company",
                "location": location or "",
                "employment_type": parsed.get("employment_type", "") or "",
                "role_category": parsed.get("role_category", "general") or "general",
                "required_skills": required,
                "preferred_skills": preferred,
                "experience_requirements": _as_list(parsed.get("experience_requirements")),
                "education_requirements": _as_list(parsed.get("education_requirements")),
                "responsibilities": _as_list(parsed.get("responsibilities")),
                "behavioural_expectations": _as_list(parsed.get("behavioural_expectations")),
                "certifications": _as_list(parsed.get("certifications")),
                "min_years_experience": float(min_years or 0.0),
            }
        )

        try:
            report = agent.analyze(candidate, job_profile, resume.raw_text or "")
        except Exception as exc:  # never let one bad posting break the ranking
            matches.append(
                {
                    "job_id": job_id,
                    "title": title or "Untitled role",
                    "company": company or "Unknown company",
                    "location": location or "",
                    "url": url or "",
                    "compatibility_score": 0.0,
                    "verdict": "Unscored",
                    "matched_skills": [],
                    "partial_skills": [],
                    "missing_skills": [],
                    "evidence": [],
                    "strengths": [],
                    "concerns": [],
                    "explanation": f"Score unavailable: {exc}",
                    "error": str(exc)[:200],
                }
            )
            continue

        data = report.model_dump()
        matches.append(
            {
                "job_id": job_id,
                "title": title or "Untitled role",
                "company": company or "Unknown company",
                "location": location or "",
                "url": url or "",
                "compatibility_score": report.overall_score,
                "verdict": data.get("verdict", ""),
                "matched_skills": data.get("matched_skills", []),
                "partial_skills": data.get("partially_matched_skills", []),
                "missing_skills": data.get("missing_skills", []),
                "evidence": data.get("evidence", []),
                "strengths": data.get("strengths", []),
                "concerns": data.get("concerns", []),
                "explanation": data.get("explanation", ""),
                "category_scores": data.get("category_scores", []),
            }
        )

    matches.sort(key=lambda m: m["compatibility_score"], reverse=True)
    for rank, match in enumerate(matches, start=1):
        match["rank"] = rank

    return {
        "matches": matches,
        "resume_id": resume.id,
        "resume_filename": resume.filename,
        "total": len(matches),
    }


@router.get("/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    job = db.get(JobAnalysis, job_id)
    if job and job.user_id != user.id:
        raise HTTPException(404, "Job analysis not found.")
    if not job:
        raise HTTPException(404, "Job analysis not found.")
    return job_to_dict(job, include_text=True)


@router.delete("/{job_id}")
def delete_job(job_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    job = db.get(JobAnalysis, job_id)
    if job and job.user_id != user.id:
        raise HTTPException(404, "Job analysis not found.")
    if not job:
        raise HTTPException(404, "Job analysis not found.")
    db.delete(job)
    db.commit()
    return {"deleted": True, "id": job_id}
