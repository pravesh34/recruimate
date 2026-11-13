"""Turn a stored ``job_postings`` row into a validated :class:`JobProfile`.

Shared by the pool ranker (``/api/jobs/match-resume``), the plan-of-approach
generator (``/api/skill-gaps/generate-for-job``) and the pool mock interview
(``/api/interviews/for-job``) so all three score postings identically.
"""
from __future__ import annotations

import json
import re

from ..schemas import JobProfile
from .skills import extract_skills


def _as_list(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if v]
    return [str(value)]


def posting_raw_text(row) -> str:
    raw = row.raw_text if isinstance(row.raw_text, str) else ""
    return raw


def posting_parsed(row) -> dict:
    parsed = row.parsed if isinstance(row.parsed, dict) else {}
    if isinstance(row.parsed, str):
        try:
            parsed = json.loads(row.parsed)
        except ValueError:
            parsed = {}
    return parsed


def build_job_profile(row) -> JobProfile:
    """Validate a posting row into a ``JobProfile``, recovering skills and the
    minimum-experience hint from the description when the parsed payload lacks
    them (board imports often carry only free text)."""
    parsed = posting_parsed(row)

    required = parsed.get("skills") or parsed.get("required_skills") or []
    preferred = parsed.get("preferred_skills") or []
    required = required if isinstance(required, list) else [required]
    preferred = preferred if isinstance(preferred, list) else [preferred]

    clean_text = re.sub(r"<[^>]+>", " ", row.raw_text or "")
    clean_text = re.sub(r"\s+", " ", clean_text).strip()

    if not required and clean_text:
        required = extract_skills(clean_text)

    min_years = parsed.get("min_years_experience")
    if not min_years and clean_text:
        match = re.search(r"(\d+)\s*\+?\s*years", clean_text, re.IGNORECASE)
        if match:
            try:
                min_years = float(match.group(1))
            except ValueError:
                min_years = 0.0

    return JobProfile.model_validate(
        {
            "job_title": row.title or "Untitled role",
            "company": row.company or "Unknown company",
            "location": row.location or "",
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
