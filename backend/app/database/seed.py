"""Idempotent demo-data seeding, callable from ``init_db()`` and the CLI scripts.

Reuses the persona/posting data from ``backend/scripts`` (single source of
truth) but writes through SQLAlchemy so seeding respects ``DATABASE_URL`` —
the raw-sqlite3 scripts always wrote to ``backend/data/recruimate.db`` and
would seed the wrong database in tests or custom deployments.

Safe to run on every boot: rows are matched and updated in place.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from ..config import settings
from .models import JobPosting, ResumeProfile, User

logger = logging.getLogger(__name__)


def seed_demo_jobs(db: Session) -> int:
    """Upsert the demo job postings (shared/global, user_id NULL)."""
    from .demo_data import DEMO_JOBS

    created = 0
    for job in DEMO_JOBS:
        parsed = {
            "skills": job["required_skills"],
            "preferred_skills": job["preferred_skills"],
            "min_years_experience": job["min_years_experience"],
            "responsibilities": [],
            "certifications": [],
            "degrees": [],
            "role_category": "general",
            "employment_type": "Full-time",
            "match_reason": "Demo posting seeded for testing.",
            "fit_score": 0.0,
            "is_demo": True,
        }
        raw_text = (
            f"Title: {job['title']}\n"
            f"Company: {job['company']}\n"
            f"Location: {job['location']}\n"
            f"Description: {job['description']}\n"
            f"Tags: {', '.join(job['required_skills'])}\n"
        )
        row = (
            db.query(JobPosting)
            .filter(JobPosting.title == job["title"], JobPosting.company == job["company"])
            .first()
        )
        if row:
            row.location = job["location"]
            row.url = job["url"]
            row.raw_text = raw_text
            row.parsed = parsed
            row.source = "demo"
            row.is_demo = True
        else:
            db.add(
                JobPosting(
                    user_id=None,
                    source="demo",
                    url=job["url"],
                    title=job["title"],
                    company=job["company"],
                    location=job["location"],
                    raw_text=raw_text,
                    parsed=parsed,
                    provider="heuristic",
                    is_demo=True,
                )
            )
            created += 1
    db.commit()
    return created


def seed_demo_candidates(db: Session) -> int:
    """Upsert the demo candidate accounts and their resume profiles."""
    from app.schemas import CandidateProfile
    from scripts.seed_demo_candidates import (
        CANDIDATES,
        DEMO_PASSWORD,
        build_resume_text,
    )
    from ..core.auth import hash_password

    created = 0
    for c in CANDIDATES:
        email = c["email"]
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.display_name = c["display_name"]
            user.password_hash = hash_password(DEMO_PASSWORD)
            user.role = "candidate"
            user.is_active = True
            user.is_demo = True
            user.is_local = False
        else:
            user = User(
                email=email,
                display_name=c["display_name"],
                password_hash=hash_password(DEMO_PASSWORD),
                role="candidate",
                is_active=True,
                is_demo=True,
                is_local=False,
            )
            db.add(user)
            db.flush()
            created += 1

        profile = {
            "name": c["display_name"],
            "headline": c["headline"],
            "email": email,
            "phone": c["phone"],
            "location": c["location"],
            "summary": c["summary"],
            "skills": c["skills"],
            "soft_skills": c["soft_skills"],
            "education": c["education"],
            "experience": c["experience"],
            "projects": c["projects"],
            "certifications": c["certifications"],
            "achievements": [],
            "resume_strengths": [],
            "resume_weaknesses": [],
            "improvement_suggestions": [],
            "unknown_fields": [],
            "years_experience": c["years_experience"],
        }
        # Validate against the real schema so nothing silently drifts.
        CandidateProfile.model_validate(profile)

        resume_text = build_resume_text(c)
        resume = (
            db.query(ResumeProfile)
            .filter(ResumeProfile.user_id == user.id, ResumeProfile.filename == c["resume_filename"])
            .first()
        )
        if resume:
            resume.raw_text = resume_text
            resume.profile = profile
            resume.provider = "demo"
            resume.pdf_path = _write_demo_pdf(user.id, resume_text, c["resume_filename"])
        else:
            db.add(
                ResumeProfile(
                    user_id=user.id,
                    filename=c["resume_filename"],
                    storage_path="",
                    pdf_path=_write_demo_pdf(user.id, resume_text, c["resume_filename"]),
                    raw_text=resume_text,
                    profile=profile,
                    provider="demo",
                )
            )
    db.commit()
    return created


def _write_demo_pdf(user_id: int, text: str, filename: str) -> str:
    """Render a demo candidate's resume to a real PDF file.

    Demo accounts ship with actual PDF documents (not placeholders), so
    "Open my resume" shows a genuine file on a fresh install.
    """
    from pathlib import Path

    from ..config import settings

    try:
        from ..services.resume_pdf import render_resume_pdf

        pdf_bytes = render_resume_pdf(text, title=Path(filename).stem or "Resume")
        target = settings.upload_path / f"demo_{user_id}_{Path(filename).stem}.pdf"
        target.write_bytes(pdf_bytes)
        try:
            target.chmod(0o600)
        except OSError:
            pass
        return str(target)
    except Exception:  # pragma: no cover - reportlab missing
        return ""


def reset_demo_data(db: Session) -> None:
    """Remove seeded demo rows so ``seed_demo_*`` can start clean (--reset)."""
    from scripts.seed_demo_candidates import CANDIDATES

    for c in CANDIDATES:
        user = db.query(User).filter(User.email == c["email"]).first()
        if not user:
            continue
        db.query(ResumeProfile).filter(ResumeProfile.user_id == user.id).delete(
            synchronize_session=False
        )
        db.delete(user)
    db.query(JobPosting).filter(JobPosting.source == "demo").delete(
        synchronize_session=False
    )
    db.commit()


def maybe_seed(db: Session) -> None:
    """Seed demo accounts + postings on first boot when configured.

    Gated on ``SEED_DEMO_ACCOUNTS`` and on auth being enabled: demo accounts
    are pointless (and unused) in trusted-local mode.
    """
    if not (settings.seed_demo_accounts and settings.auth_enabled):
        return
    jobs = seed_demo_jobs(db)
    candidates = seed_demo_candidates(db)
    if jobs or candidates:
        logger.info(
            "Demo seed: %d new candidate account(s), %d new job posting(s)",
            candidates,
            jobs,
        )


def dump_state(db: Session) -> dict:
    """Small helper for CLI output."""
    return {
        "users": db.query(User).filter(User.is_demo.is_(True)).count(),
        "resumes": db.query(ResumeProfile).filter(ResumeProfile.provider == "demo").count(),
        "jobs": db.query(JobPosting).filter(JobPosting.source == "demo").count(),
    }
