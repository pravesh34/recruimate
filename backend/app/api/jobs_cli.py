"""Jobs CLI integration endpoints (LinkedIn / Indeed / public boards).

Everything in this router is scoped to the authenticated candidate. The CLI
itself is optional: when the binary is missing or the feature is disabled the
endpoints report a clear reason instead of failing.

Safety rules baked into this module:

* only read-only CLI commands are ever executed (never ``apply``);
* the CLI's own credentials/session are never read or returned;
* no endpoint applies to a job, sends a message or contacts an employer.
"""
from __future__ import annotations

import datetime as dt
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..config import settings
from ..database.models import (
    CliSyncRun,
    JobBookmark,
    JobPosting,
    PipelineEntry,
    User,
    get_db,
)
from ..services import jobs_cli
from ..services.job_normalize import (
    dedupe_key,
    normalize_job,
    partition_errors,
    partition_jobs,
)
from .deps import get_current_user, iso
from .schemas import CliImportRequest, CliSearchRequest, CliTrackRequest

router = APIRouter(prefix="/api/jobs-cli", tags=["jobs-cli"])

# Sources whose listings may be imported into the pool.
IMPORTABLE_SOURCES = {"linkedin", "indeed", "yzi", "civicinfo", "translink"}


def _require_cli() -> None:
    if not jobs_cli.is_available():
        raise HTTPException(503, jobs_cli.unavailable_reason())


def _pool_row_to_dict(row: JobPosting) -> dict[str, Any]:
    return {
        "id": row.id,
        "title": row.title,
        "company": row.company,
        "location": row.location,
        "url": row.url,
        "apply_url": row.apply_url or row.url,
        "source": row.source,
        "remote": bool(row.remote),
        "employment_type": row.employment_type,
        "experience_level": row.experience_level,
        "salary_min": row.salary_min,
        "salary_max": row.salary_max,
        "salary_currency": row.salary_currency,
        "salary_text": row.salary_text,
        "posted_at": row.posted_at,
        "skills": (row.parsed or {}).get("skills", []),
        "created_at": iso(row.created_at),
    }


# --------------------------------------------------------------------------- #
# Status
# --------------------------------------------------------------------------- #
@router.get("/status")
async def cli_status(user: User = Depends(get_current_user)):
    """Report whether the Jobs CLI integration can be used right now."""
    payload: dict[str, Any] = {
        "enabled": bool(settings.jobs_cli_enabled),
        "available": jobs_cli.is_available(),
        "binary": jobs_cli.binary_path() or "",
        "reason": jobs_cli.unavailable_reason(),
        "sources": list(jobs_cli.CLI_SOURCES),
        "read_only": True,
        "auto_apply": False,
        "note": (
            "RecruiMate uses the CLI for discovery only. It never applies to a job "
            "or contacts an employer — you always apply yourself."
        ),
    }
    if jobs_cli.is_available():
        try:
            result = await jobs_cli.sources_status(user_id=user.id)
            payload["source_status"] = result.data
            payload["cli_meta"] = {
                "duration_ms": result.duration_ms,
                "schema_version": result.meta.get("schema_version", ""),
            }
        except jobs_cli.JobsCliError as exc:
            payload["source_status_error"] = str(exc)
    return payload


# --------------------------------------------------------------------------- #
# Search (read-only, nothing is persisted)
# --------------------------------------------------------------------------- #
@router.post("/search")
async def cli_search(
    payload: CliSearchRequest,
    user: User = Depends(get_current_user),
):
    """Search the CLI's sources and return normalised listings.

    Nothing is written to the database here: the candidate picks what to add
    to the pool with ``/import``. Identical searches inside the cache window
    are served from memory.
    """
    _require_cli()
    cache_key = "|".join(
        [
            str(user.id),
            payload.query.strip().lower(),
            payload.location.strip().lower(),
            ",".join(sorted(payload.sources)),
            "remote" if payload.remote else "onsite",
            str(payload.limit),
            payload.country.strip().upper(),
        ]
    )
    cached = jobs_cli.cache_get(cache_key)
    if cached is not None:
        return {**cached, "cached": True}

    try:
        result = await jobs_cli.search(
            query=payload.query,
            location=payload.location,
            sources=payload.sources or None,
            remote=payload.remote,
            limit=payload.limit,
            offset=payload.offset,
            country=payload.country,
            user_id=user.id,
        )
    except jobs_cli.JobsCliError as exc:
        raise HTTPException(502 if exc.retryable else 400, str(exc)) from exc

    raw_jobs = partition_jobs(result.data)
    listings = [normalize_job(job) for job in raw_jobs]
    response = {
        "listings": listings[: payload.limit],
        "total": len(listings),
        "sources": sorted({item["source"] for item in listings if item["source"]}),
        "source_errors": partition_errors(result.data),
        "duration_ms": result.duration_ms,
        "cached": False,
    }
    jobs_cli.cache_set(cache_key, response)
    return response


# --------------------------------------------------------------------------- #
# Import into the pool
# --------------------------------------------------------------------------- #
def _upsert_job(db: Session, user: User, job: dict[str, Any]) -> tuple[str, JobPosting | None]:
    """Insert or update a pool row for one normalised job.

    Returns ``("created"|"updated"|"skipped", row)``. A job whose
    cross-source key already exists for this user is updated in place, so the
    same LinkedIn/Indeed posting never appears twice in the pool.
    """
    source = job.get("source") or "unknown"
    if source not in IMPORTABLE_SOURCES:
        return "skipped", None

    key = job.get("dedupe_key") or dedupe_key(job.get("title", ""), job.get("company", ""), job.get("location", ""))
    existing = (
        db.query(JobPosting)
        .filter(JobPosting.user_id == user.id)
        .filter(JobPosting.dedupe_key == key)
        .first()
    )
    parsed = {
        "skills": job.get("skills", []),
        "preferred_skills": [],
        "min_years_experience": 0,
        "responsibilities": [],
        "certifications": [],
        "degrees": [],
        "role_category": "",
        "employment_type": job.get("employment_type", ""),
        "match_reason": f"Imported from {source}.",
        "fit_score": 0.0,
        "source": source,
        "tags": job.get("tags", []),
    }
    if existing:
        existing.title = job.get("title") or existing.title
        existing.company = job.get("company") or existing.company
        existing.location = job.get("location") or existing.location
        existing.raw_text = job.get("description") or existing.raw_text
        existing.parsed = parsed
        existing.apply_url = job.get("apply_url", "") or existing.apply_url
        existing.remote = bool(job.get("remote"))
        existing.employment_type = job.get("employment_type", "") or existing.employment_type
        existing.experience_level = job.get("experience_level", "") or existing.experience_level
        existing.salary_min = job.get("salary_min")
        existing.salary_max = job.get("salary_max")
        existing.salary_currency = job.get("salary_currency", "")
        existing.salary_text = job.get("salary_text", "")
        existing.posted_at = job.get("posted_at", "") or existing.posted_at
        existing.source_job_id = job.get("source_job_id", "") or existing.source_job_id
        return "updated", existing

    row = JobPosting(
        user_id=user.id,
        source=source,
        url=job.get("source_url", "") or job.get("apply_url", ""),
        title=job.get("title", "")[:255],
        company=job.get("company", "")[:255],
        location=job.get("location", "")[:255],
        raw_text=job.get("description", "")[:40000],
        parsed=parsed,
        provider="heuristic",
        is_demo=False,
        source_job_id=job.get("source_job_id", "")[:200],
        dedupe_key=key,
        apply_url=job.get("apply_url", "")[:1024],
        remote=bool(job.get("remote")),
        employment_type=job.get("employment_type", "")[:64],
        experience_level=job.get("experience_level", "")[:64],
        salary_min=job.get("salary_min"),
        salary_max=job.get("salary_max"),
        salary_currency=job.get("salary_currency", "")[:16],
        salary_text=job.get("salary_text", "")[:255],
        posted_at=job.get("posted_at", "")[:32],
    )
    db.add(row)
    db.flush()
    return "created", row


@router.post("/import")
def cli_import(
    payload: CliImportRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Add selected listings to the caller's pool (de-duplicated)."""
    created = updated = skipped = 0
    rows: list[JobPosting] = []
    for item in payload.listings[:100]:
        job = normalize_job(item)
        outcome, row = _upsert_job(db, user, job)
        if outcome == "created":
            created += 1
        elif outcome == "updated":
            updated += 1
        else:
            skipped += 1
        if row is not None:
            rows.append(row)
    db.commit()
    total = db.query(JobPosting).filter(JobPosting.user_id == user.id).count()
    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "pool_size": total,
        "jobs": [_pool_row_to_dict(row) for row in rows],
    }


# --------------------------------------------------------------------------- #
# Background synchronisation
# --------------------------------------------------------------------------- #
async def _run_sync(db: Session, user_id: int, run_id: int, params: dict[str, Any]) -> None:
    """Background worker: search the CLI and import everything into the pool."""
    from ..database.models import User

    run = db.get(CliSyncRun, run_id)
    if run is None:
        return
    user = db.get(User, user_id)
    if user is None:
        return
    try:
        result = await jobs_cli.search(
            query=params.get("query", ""),
            location=params.get("location", ""),
            sources=params.get("sources") or None,
            remote=bool(params.get("remote")),
            limit=int(params.get("limit", 25)),
            country=params.get("country", ""),
            user_id=user_id,
        )
        created = updated = skipped = 0
        for raw in partition_jobs(result.data):
            job = normalize_job(raw)
            outcome, _ = _upsert_job(db, user, job)
            if outcome == "created":
                created += 1
            elif outcome == "updated":
                updated += 1
            else:
                skipped += 1
        db.commit()
        run.imported = created
        run.updated = updated
        run.skipped = skipped
        run.status = "done"
        run.error = ""
    except jobs_cli.JobsCliError as exc:
        db.rollback()
        run.status = "error"
        run.error = str(exc)[:500]
    except Exception as exc:  # pragma: no cover - defensive
        db.rollback()
        run.status = "error"
        run.error = str(exc)[:500]
    run.finished_at = dt.datetime.now(dt.timezone.utc)
    db.commit()


@router.post("/sync")
async def cli_sync(
    payload: CliSearchRequest,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Start a background synchronisation of the CLI's sources into the pool."""
    _require_cli()
    run = CliSyncRun(
        user_id=user.id,
        source=",".join(payload.sources) if payload.sources else "linkedin,indeed",
        status="running",
        params=payload.model_dump(),
        started_at=dt.datetime.now(dt.timezone.utc),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    background.add_task(_run_sync, db, user.id, run.id, payload.model_dump())
    return {"run_id": run.id, "status": run.status}


@router.get("/sync/{run_id}")
def cli_sync_status(
    run_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Progress of one synchronisation run (own runs only)."""
    run = db.get(CliSyncRun, run_id)
    if not run or run.user_id != user.id:
        raise HTTPException(404, "Sync run not found.")
    return {
        "id": run.id,
        "status": run.status,
        "source": run.source,
        "imported": run.imported,
        "updated": run.updated,
        "skipped": run.skipped,
        "error": run.error,
        "started_at": iso(run.started_at),
        "finished_at": iso(run.finished_at),
    }


@router.get("/sync")
def cli_sync_runs(
    limit: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = (
        db.query(CliSyncRun)
        .filter(CliSyncRun.user_id == user.id)
        .order_by(CliSyncRun.id.desc())
        .limit(min(limit, 50))
        .all()
    )
    return {
        "runs": [
            {
                "id": r.id,
                "status": r.status,
                "source": r.source,
                "imported": r.imported,
                "updated": r.updated,
                "skipped": r.skipped,
                "error": r.error,
                "started_at": iso(r.started_at),
                "finished_at": iso(r.finished_at),
            }
            for r in rows
        ]
    }


# --------------------------------------------------------------------------- #
# Browse imported listings (filters, search, pagination)
# --------------------------------------------------------------------------- #
@router.get("/listings")
def cli_listings(
    q: str = "",
    source: str = "",
    location: str = "",
    remote: str = "",
    experience: str = "",
    employment_type: str = "",
    min_salary: float | None = None,
    posted_after: str = "",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List the caller's imported listings with filters, search and paging."""
    query = db.query(JobPosting).filter(
        JobPosting.user_id == user.id,
        JobPosting.source.in_(IMPORTABLE_SOURCES),
    )
    if q:
        pattern = f"%{q.strip().lower()}%"
        query = query.filter(
            (JobPosting.title.ilike(pattern)) | (JobPosting.company.ilike(pattern))
        )
    if source:
        query = query.filter(JobPosting.source == source.strip().lower())
    if location:
        query = query.filter(JobPosting.location.ilike(f"%{location.strip()}%"))
    if remote in ("true", "1", "yes"):
        query = query.filter(JobPosting.remote.is_(True))
    elif remote in ("false", "0", "no"):
        query = query.filter(JobPosting.remote.is_(False))
    if experience:
        query = query.filter(JobPosting.experience_level.ilike(f"%{experience.strip()}%"))
    if employment_type:
        query = query.filter(JobPosting.employment_type.ilike(f"%{employment_type.strip()}%"))
    if min_salary:
        query = query.filter(
            (JobPosting.salary_max.isnot(None) & (JobPosting.salary_max >= min_salary))
            | (JobPosting.salary_min.isnot(None) & (JobPosting.salary_min >= min_salary))
        )
    if posted_after:
        query = query.filter(JobPosting.posted_at >= posted_after.strip()[:32])

    total = query.count()
    rows = (
        query.order_by(JobPosting.posted_at.desc(), JobPosting.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "jobs": [_pool_row_to_dict(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
    }


# --------------------------------------------------------------------------- #
# Bookmarks
# --------------------------------------------------------------------------- #
@router.get("/bookmarks")
def list_bookmarks(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = (
        db.query(JobBookmark)
        .filter(JobBookmark.user_id == user.id)
        .order_by(JobBookmark.id.desc())
        .limit(200)
        .all()
    )
    return {
        "bookmarks": [
            {
                "id": b.id,
                "job_posting_id": b.job_posting_id,
                "title": b.title,
                "company": b.company,
                "url": b.url,
                "apply_url": b.apply_url,
                "source": b.source,
                "note": b.note,
                "created_at": iso(b.created_at),
            }
            for b in rows
        ]
    }


@router.post("/bookmark")
def create_bookmark(
    payload: CliTrackRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Bookmark a job from the caller's pool."""
    if payload.job_posting_id is None:
        raise HTTPException(400, "job_posting_id is required.")
    row = db.get(JobPosting, payload.job_posting_id)
    if not row or row.user_id != user.id:
        raise HTTPException(404, "Pool job not found.")
    existing = (
        db.query(JobBookmark)
        .filter(JobBookmark.user_id == user.id, JobBookmark.job_posting_id == row.id)
        .first()
    )
    if existing:
        if payload.note:
            existing.note = payload.note[:2000]
        db.commit()
        return {"bookmarked": True, "id": existing.id}
    bookmark = JobBookmark(
        user_id=user.id,
        job_posting_id=row.id,
        title=row.title,
        company=row.company,
        url=row.url,
        apply_url=row.apply_url or row.url,
        source=row.source,
        note=payload.note[:2000],
    )
    db.add(bookmark)
    db.commit()
    db.refresh(bookmark)
    return {"bookmarked": True, "id": bookmark.id}


@router.delete("/bookmark/{bookmark_id}")
def delete_bookmark(
    bookmark_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    bookmark = db.get(JobBookmark, bookmark_id)
    if not bookmark or bookmark.user_id != user.id:
        raise HTTPException(404, "Bookmark not found.")
    db.delete(bookmark)
    db.commit()
    return {"deleted": True, "id": bookmark_id}


# --------------------------------------------------------------------------- #
# Application tracking (never auto-applies)
# --------------------------------------------------------------------------- #
@router.post("/track")
def track_application(
    payload: CliTrackRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Start tracking an application for one of the caller's pool jobs.

    This only records the candidate's own intent (status, notes, follow-up
    date). RecruiMate never submits an application or contacts the employer.
    """
    if payload.job_posting_id is None:
        raise HTTPException(400, "job_posting_id is required.")
    row = db.get(JobPosting, payload.job_posting_id)
    if not row or row.user_id != user.id:
        raise HTTPException(404, "Pool job not found.")
    existing = (
        db.query(PipelineEntry)
        .filter(PipelineEntry.user_id == user.id, PipelineEntry.job_posting_id == row.id)
        .first()
    )
    if existing:
        return {"tracked": True, "entry_id": existing.id}
    entry = PipelineEntry(
        user_id=user.id,
        job_posting_id=row.id,
        title=row.title[:255],
        company=row.company[:255],
        url=row.url[:1024],
        source=row.source[:64],
        status=payload.status or "new",
        notes=payload.note[:4000],
        apply_url=(row.apply_url or row.url)[:1024],
        source_job_id=row.source_job_id[:200],
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return {"tracked": True, "entry_id": entry.id}


@router.patch("/track/{entry_id}")
def update_tracking(
    entry_id: int,
    payload: CliTrackRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update the status/notes of a tracked application (own entries only)."""
    entry = db.get(PipelineEntry, entry_id)
    if not entry or entry.user_id != user.id:
        raise HTTPException(404, "Pipeline entry not found.")
    if payload.status:
        entry.status = payload.status[:32]
    if payload.note is not None:
        entry.notes = payload.note[:4000]
    db.commit()
    return {"updated": True, "entry_id": entry.id}
