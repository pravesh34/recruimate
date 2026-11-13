"""Job description analysis endpoints."""
from __future__ import annotations

import json
import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..agents.job_agent import JobAgent
from ..database.models import JobAnalysis, JobPosting, User, ensure_default_user, get_db
from ..gateway import GatewayManager
from ..schemas import CandidateProfile
from ..services.job_import import SOURCES, ImportError as BoardImportError, fetch_postings
from ..services.pool_insights import candidate_from_resume, resolve_resume
from ..services.posting_profile import build_job_profile
from ..services.skills import detect_role_category, extract_skills
from ..utils.web import UnsafeURLError, fetch_job_posting
from .deps import get_current_user, get_gateway, iso
from .schemas import JobAnalyzeRequest, PoolAddRequest, PoolImportRequest

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
    include_shared: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Search the caller's target job pool and rank it by compatibility.

    Given a resume, computes a deterministic compatibility score between the
    resume and every posting in the caller's pool, then returns the jobs
    ranked by score (highest first) so the candidate can shortlist and apply.

    Args:
        resume_id: Resume profile id. Uses the most recent resume if omitted.
        include_shared: Also score shared/demo postings (``user_id`` NULL).

    Returns:
        ``{"matches": [...]}`` where each match carries the job identity,
        the compatibility score, and the full explainable report
        (matched / partial / missing skills, evidence, strengths, concerns).
    """
    from ..agents.compatibility_agent import CompatibilityAgent
    from ..database.models import ResumeProfile

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

    query = db.query(JobPosting).filter(JobPosting.user_id == user.id)
    if include_shared:
        query = db.query(JobPosting).filter(
            (JobPosting.user_id == user.id) | (JobPosting.user_id.is_(None))
        )
    rows = query.order_by(JobPosting.created_at.desc(), JobPosting.id.desc()).all()
    if not rows:
        return {
            "matches": [],
            "resume_id": resume.id,
            "message": "Your target job pool is empty. Import real jobs or add one manually.",
        }

    agent = CompatibilityAgent()
    matches: list[dict] = []

    for row in rows:
        try:
            job_profile = build_job_profile(row)
        except Exception as exc:  # never let one bad posting break the ranking
            matches.append(_unscored_match(row, f"Score unavailable: {exc}"))
            continue

        try:
            report = agent.analyze(candidate, job_profile, resume.raw_text or "")
        except Exception as exc:  # never let one bad posting break the ranking
            matches.append(_unscored_match(row, f"Score unavailable: {exc}"))
            continue

        data = report.model_dump()
        matches.append(
            {
                "job_id": row.id,
                "title": row.title or "Untitled role",
                "company": row.company or "Unknown company",
                "location": row.location or "",
                "url": row.url or "",
                "source": row.source or "",
                "in_pool": row.user_id == user.id,
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


def _unscored_match(row: JobPosting, explanation: str) -> dict:
    return {
        "job_id": row.id,
        "title": row.title or "Untitled role",
        "company": row.company or "Unknown company",
        "location": row.location or "",
        "url": row.url or "",
        "source": row.source or "",
        "in_pool": False,
        "compatibility_score": 0.0,
        "verdict": "Unscored",
        "matched_skills": [],
        "partial_skills": [],
        "missing_skills": [],
        "evidence": [],
        "strengths": [],
        "concerns": [],
        "explanation": explanation,
        "error": explanation[:200],
    }




# --------------------------------------------------------------------------- #
# Target job pool (per-candidate)
# --------------------------------------------------------------------------- #
def _pool_row_to_dict(row: JobPosting) -> dict:
    parsed = row.parsed if isinstance(row.parsed, dict) else {}
    return {
        "id": row.id,
        "title": row.title,
        "company": row.company,
        "location": row.location,
        "url": row.url,
        "source": row.source,
        "skills": (parsed.get("skills") or [])[:12],
        "min_years_experience": parsed.get("min_years_experience", 0),
        "created_at": iso(row.created_at),
    }


def _upsert_pool_postings(
    db: Session, user: User, postings: list[dict], default_source: str
) -> tuple[int, int]:
    """Insert new pool rows and update existing ones (matched on URL)."""
    from ..services.job_import import strip_html

    existing = {
        row.url: row
        for row in db.query(JobPosting).filter(JobPosting.user_id == user.id).all()
        if row.url
    }
    created = 0
    updated = 0
    for posting in postings:
        clean_text = re.sub(r"\s+", " ", strip_html(posting["description"])).strip()
        # Skills: board tags first (they are curated), then anything the
        # deterministic extractor recognises in the description.
        skills: list[str] = []
        seen: set[str] = set()
        for skill in [*posting["tags"], *extract_skills(f"{clean_text} {', '.join(posting['tags'])}")]:
            key = skill.strip().lower()
            if key and key not in seen:
                seen.add(key)
                skills.append(skill.strip())
        parsed = {
            "skills": skills[:25],
            "preferred_skills": [],
            "min_years_experience": min_years_hint(clean_text),
            "responsibilities": [],
            "certifications": [],
            "degrees": [],
            "role_category": detect_role_category(posting["title"], clean_text),
            "employment_type": "Full-time",
            "match_reason": f"Imported from {posting['source']}.",
            "fit_score": 0.0,
        }
        row = existing.get(posting["url"])
        if row:
            row.title = posting["title"]
            row.company = posting["company"]
            row.location = posting["location"]
            row.raw_text = posting["raw_text"]
            row.parsed = parsed
            row.source = posting.get("source", default_source)
            updated += 1
        else:
            db.add(
                JobPosting(
                    user_id=user.id,
                    source=posting.get("source", default_source),
                    url=posting["url"],
                    title=posting["title"],
                    company=posting["company"],
                    location=posting["location"],
                    raw_text=posting["raw_text"],
                    parsed=parsed,
                    provider="heuristic",
                    is_demo=False,
                )
            )
            created += 1
    db.commit()
    return created, updated


def min_years_hint(text: str) -> float:
    match = re.search(r"(\d+)\s*\+?\s*years", text or "", re.IGNORECASE)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return 0.0
    return 0.0


@router.post("/pool/import")
async def import_to_pool(
    payload: PoolImportRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Pull real postings from a job board straight into the caller's pool."""
    try:
        postings = await fetch_postings(payload.source, payload.query, payload.limit)
    except BoardImportError as exc:
        raise HTTPException(502, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    created, updated = _upsert_pool_postings(db, user, postings, payload.source)
    total = db.query(JobPosting).filter(JobPosting.user_id == user.id).count()
    return {
        "imported": created,
        "updated": updated,
        "pool_size": total,
        "source": payload.source,
        "query": payload.query,
    }


@router.get("/pool")
def list_pool(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (
        db.query(JobPosting)
        .filter(JobPosting.user_id == user.id)
        .order_by(JobPosting.created_at.desc(), JobPosting.id.desc())
        .limit(200)
        .all()
    )
    return {"jobs": [_pool_row_to_dict(r) for r in rows], "total": len(rows)}


@router.post("/pool/add")
async def add_to_pool(
    payload: PoolAddRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Add a single job to the pool from a public URL or pasted text."""
    description = (payload.description or "").strip()
    url = (payload.url or "").strip()
    if not description and url:
        try:
            description = await fetch_job_posting(url)
        except UnsafeURLError as exc:
            raise HTTPException(400, f"Unsafe or invalid URL: {exc}") from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except Exception as exc:
            raise HTTPException(422, f"Could not fetch that posting: {exc}") from exc
    if len(description) < 40:
        raise HTTPException(400, "Paste a job description (at least 40 characters) or a public URL.")

    clean_text = re.sub(r"\s+", " ", description).strip()
    title = (payload.title or clean_text.splitlines()[0] if clean_text else "")[:255]
    company = payload.company.strip()
    if not company:
        match = re.search(r"(?:at|Company:)\s+([A-Z][\w&.\- ]{1,60})", clean_text)
        company = match.group(1).strip() if match else ""
    skills = extract_skills(clean_text)
    parsed = {
        "skills": skills[:25],
        "preferred_skills": [],
        "min_years_experience": min_years_hint(clean_text),
        "responsibilities": [],
        "certifications": [],
        "degrees": [],
        "role_category": detect_role_category(title, clean_text),
        "employment_type": "Full-time",
        "match_reason": "Added manually.",
        "fit_score": 0.0,
    }
    row = JobPosting(
        user_id=user.id,
        source="manual",
        url=url[:1024],
        title=title,
        company=company[:255],
        location=(payload.location or "").strip()[:255],
        raw_text=clean_text[:40000],
        parsed=parsed,
        provider="heuristic",
        is_demo=False,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"added": True, "job": _pool_row_to_dict(row)}


@router.delete("/pool/{job_id}")
def delete_pool_job(
    job_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    """Remove a posting from the caller's pool (shared postings are protected)."""
    row = db.get(JobPosting, job_id)
    if not row or row.user_id != user.id:
        raise HTTPException(404, "Pool job not found.")
    db.delete(row)
    db.commit()
    return {"deleted": True, "id": job_id}


@router.get("/pool/sources")
def pool_sources():
    """Boards the importer can pull from."""
    return {"sources": list(SOURCES)}


@router.get("/pool/insights")
def pool_insights(
    resume_id: int | None = None,
    include_shared: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Aggregate every pool job against the resume: which skills unlock the
    most jobs, how strong the pool fit is, and where the best shot is."""
    from ..services.pool_insights import analyze_pool, skill_unlocks

    resume = resolve_resume(db, user.id, resume_id)
    if resume is None:
        raise HTTPException(404, "Upload a resume first.")

    query = db.query(JobPosting).filter(JobPosting.user_id == user.id)
    if include_shared:
        query = db.query(JobPosting).filter(
            (JobPosting.user_id == user.id) | (JobPosting.user_id.is_(None))
        )
    rows = query.order_by(JobPosting.created_at.desc(), JobPosting.id.desc()).all()
    if not rows:
        return {
            "resume_id": resume.id,
            "jobs_scored": 0,
            "skill_unlocks": [],
            "message": "Your target job pool is empty. Import real jobs first.",
        }

    analysis = analyze_pool(candidate_from_resume(resume), resume.raw_text or "", rows)
    scores = analysis["scores"]
    best = max(analysis["job_scores"], key=lambda j: j["score"]) if analysis["job_scores"] else None
    return {
        "resume_id": resume.id,
        "jobs_scored": len(scores),
        "average_score": round(sum(scores) / len(scores), 1) if scores else 0.0,
        "best_job": best,
        "skill_unlocks": skill_unlocks(analysis, limit=12),
    }


def _tailor_payload(db: Session, user: User, job_id: int, resume_id: int | None):
    """Shared tailoring core: resolve posting + resume, score fit, tailor."""
    from ..agents.compatibility_agent import CompatibilityAgent
    from ..services.tailor_service import tailor_for_job

    posting = db.get(JobPosting, job_id)
    if not posting or (posting.user_id is not None and posting.user_id != user.id):
        raise HTTPException(404, "Pool job not found.")
    resume = resolve_resume(db, user.id, resume_id)
    if resume is None:
        raise HTTPException(404, "Upload a resume first.")

    try:
        job_profile = build_job_profile(posting)
    except Exception as exc:
        raise HTTPException(422, f"That posting could not be parsed: {exc}") from exc

    try:
        candidate = candidate_from_resume(resume)
    except Exception as exc:
        raise HTTPException(400, f"Resume profile could not be parsed: {exc}") from exc

    tailor = tailor_for_job(candidate, job_profile, posting.raw_text or "")
    fit = CompatibilityAgent().analyze(candidate, job_profile, resume.raw_text or "")

    def _skill_name(item) -> str:
        if isinstance(item, dict):
            return item.get("skill", "")
        return getattr(item, "skill", "")

    tailor["fit_score"] = round(fit.overall_score, 1)
    tailor["matched_from_agent"] = [s for s in map(_skill_name, fit.matched_skills or []) if s][:8]
    tailor["job"] = {"id": posting.id, "title": posting.title, "company": posting.company, "url": posting.url}
    tailor["resume_id"] = resume.id
    return tailor


@router.post("/tailor")
def tailor_resume_for_job(
    job_id: int,
    resume_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Tailor the caller's resume for one pool job: bullet ordering, skill
    tags, fit score and a cover-letter draft. No content is invented."""
    return _tailor_payload(db, user, job_id, resume_id)


@router.get("/tailor/export")
def tailor_export(
    job_id: int,
    resume_id: int | None = None,
    format: str = "html",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Download the tailored application as print-ready HTML or Markdown."""
    from fastapi.responses import Response

    from ..services.tailor_service import tailor_html, tailor_markdown

    tailor = _tailor_payload(db, user, job_id, resume_id)
    job = tailor["job"]
    if format == "md":
        content = tailor_markdown(tailor, job["title"], job["company"])
        return Response(
            content=content,
            media_type="text/markdown; charset=utf-8",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="tailored-{job["id"]}.md"'
                )
            },
        )
    content = tailor_html(tailor, job["title"], job["company"])
    return Response(
        content=content,
        media_type="text/html; charset=utf-8",
        headers={"Content-Disposition": f'inline; filename="tailored-{job["id"]}.html"'},
    )


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
