"""Cross-pool insight aggregation: which skills unlock the most target jobs?"""
from __future__ import annotations

from collections import Counter, defaultdict  # noqa: F401

from ..agents.compatibility_agent import CompatibilityAgent
from ..schemas import CompatibilityReport, SkillMatch
from .posting_profile import build_job_profile


def resolve_resume(db, user_id: int, resume_id: int | None):
    """The caller's chosen resume, or the most recent one."""
    from ..database.models import ResumeProfile

    return (
        db.query(ResumeProfile)
        .filter(ResumeProfile.user_id == user_id, ResumeProfile.id == resume_id)
        .first()
        if resume_id
        else db.query(ResumeProfile)
        .filter(ResumeProfile.user_id == user_id)
        .order_by(ResumeProfile.created_at.desc(), ResumeProfile.id.desc())
        .first()
    )


def candidate_from_resume(resume):
    """Validate the stored JSON profile into a CandidateProfile."""
    import json

    from ..schemas import CandidateProfile

    raw_profile = resume.profile or "{}"
    profile_dict = json.loads(raw_profile) if isinstance(raw_profile, str) else (raw_profile or {})
    return CandidateProfile.model_validate(profile_dict)


def analyze_pool(candidate, resume_text: str, rows) -> dict:
    """Score every pool posting against one candidate profile.

    Returns ``{"job_scores": [...], "missing": {...}, "partial": {...},
    "scores": [...]}`` where ``missing``/``partial`` map lowercase skill ->
    {"label", "count", "jobs": [...]}. One broken posting never breaks the
    aggregation.
    """
    agent = CompatibilityAgent()
    job_scores: list[dict] = []
    missing: dict[str, dict] = {}
    partial: dict[str, dict] = {}

    for row in rows:
        try:
            profile = build_job_profile(row)
        except Exception:
            continue
        try:
            report = agent.analyze(candidate, profile, resume_text or "")
        except Exception:
            continue

        job_scores.append(
            {
                "job_id": row.id,
                "title": row.title or "Untitled role",
                "company": row.company or "Unknown company",
                "score": round(report.overall_score, 1),
                "verdict": report.verdict,
            }
        )
        for item in report.missing_skills:
            _tally(missing, item, row)
        for item in report.partially_matched_skills:
            _tally(partial, item, row)

    return {
        "job_scores": job_scores,
        "missing": missing,
        "partial": partial,
        "scores": [j["score"] for j in job_scores],
    }


def _tally(bucket: dict, item: SkillMatch, row) -> None:
    label = (item.skill or "").strip()
    if not label:
        return
    key = label.lower()
    record = bucket.setdefault(key, {"label": label, "count": 0, "jobs": []})
    record["count"] += 1
    if len(record["jobs"]) < 6:
        record["jobs"].append({"job_id": row.id, "title": row.title or "Untitled role"})


def skill_unlocks(analysis: dict, limit: int = 12) -> list[dict]:
    """Missing skills ranked by how many pool jobs they block."""
    missing, partial = analysis["missing"], analysis["partial"]
    items = []
    for key, record in missing.items():
        items.append(
            {
                "skill": record["label"],
                "unlocks": record["count"],
                "jobs": record["jobs"],
                "partial": partial.get(key, {}).get("count", 0) > 0,
            }
        )
    items.sort(key=lambda i: (-i["unlocks"], i["skill"].lower()))
    return items[:limit]


def pool_report(analysis: dict, max_skills: int = 6) -> CompatibilityReport:
    """A synthetic CompatibilityReport covering the whole pool.

    Feeds the ordinary roadmap generator so a combined plan reuses all of the
    existing machinery (templates, priorities, hour estimates, task tracking).
    """
    scores = analysis["scores"]
    average = round(sum(scores) / len(scores), 1) if scores else 0.0
    verdict = (
        "Strong match" if average >= 70 else "Good match" if average >= 55 else
        "Stretch match" if average >= 35 else "Low match"
    ) if scores else "Unscored"

    missing_sorted = sorted(
        analysis["missing"].values(), key=lambda r: (-r["count"], r["label"].lower())
    )[:max_skills]
    missing_used = {r["label"].lower() for r in missing_sorted}
    partial_sorted = sorted(
        (r for k, r in analysis["partial"].items() if k not in missing_used),
        key=lambda r: (-r["count"], r["label"].lower()),
    )[:max_skills]

    return CompatibilityReport(
        overall_score=average,
        verdict=verdict,
        category_scores=[],
        matched_skills=[],
        partially_matched_skills=[
            SkillMatch(skill=r["label"], similarity=0.4) for r in partial_sorted
        ],
        missing_skills=[
            SkillMatch(skill=r["label"], similarity=0.0) for r in missing_sorted
        ],
        evidence=[],
        explanation=(
            f"Combined view across {len(scores)} target jobs. Each gap is ranked "
            "by how many postings list it as required."
        ),
        strengths=[],
        concerns=[],
        method="pool-aggregate",
    )
