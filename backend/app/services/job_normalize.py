"""Normalisation and cross-source de-duplication for imported job listings.

The Jobs CLI, Remotive and RemoteOK all describe the same job with different
field names and different levels of detail. Everything is funnelled through
:func:`normalize_job` so the pool, the ranking and the compatibility agent
always see the same shape, and through :func:`dedupe_key` so the same role
imported from LinkedIn *and* Indeed lands in the pool only once.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any

from .skills import extract_skills

_WS = re.compile(r"\s+")
_PUNCT = re.compile(r"[^\w\s]+")

# Words that carry no identity in a job title.
_NOISE_WORDS = {
    "a", "an", "the", "and", "or", "of", "in", "at", "to", "for", "with",
    "senior", "junior", "staff", "lead", "principal", "entry", "level",
    "remote", "full", "part", "time", "contract", "permanent", "intern",
    "graduate", "trainee", "engineer", "developer", "manager",
}


def _clean(value: Any) -> str:
    return _WS.sub(" ", str(value or "")).strip()


def _slug(value: str) -> str:
    return _PUNCT.sub(" ", (value or "").lower()).strip()


def _first(values: list[str]) -> str:
    for value in values:
        if value:
            return value
    return ""


def dedupe_key(title: str, company: str, location: str) -> str:
    """Stable key used to detect the same role across different sources.

    Title and company are compared loosely (case/punctuation insensitive, a
    few noise words removed) so "Senior Backend Engineer" and "Backend
    Engineer" at the same company in the same city collapse to one key.
    """
    def norm(text: str) -> str:
        words = [w for w in _slug(text).split() if w not in _NOISE_WORDS]
        return " ".join(words)

    basis = "|".join([norm(title), norm(company), norm(location).lower()])
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:20]


def _parse_date(value: Any) -> str:
    """Normalise a date to ``YYYY-MM-DD`` (empty string when unknown)."""
    text = _clean(value)
    if not text:
        return ""
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text[: len(fmt) + 6].strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    return match.group(0) if match else ""


def _salary(job: dict[str, Any]) -> tuple[float | None, float | None, str, str]:
    compensation = job.get("compensation") or {}
    if not isinstance(compensation, dict):
        compensation = {}
    minimum = maximum = None
    for amount in compensation.get("amounts") or []:
        if not isinstance(amount, dict):
            continue
        if amount.get("min") is not None:
            minimum = float(amount["min"])
        if amount.get("max") is not None:
            maximum = float(amount["max"])
        if minimum is not None or maximum is not None:
            break
    summary = _clean(compensation.get("summary"))
    if minimum is None and maximum is None:
        # Fall back to a plain number in the summary text ("CA$100k-140k").
        numbers = re.findall(r"(\d[\d,\.]*)\s*([kKmM]?)", summary)
        values = []
        for raw, suffix in numbers:
            try:
                value = float(raw.replace(",", ""))
            except ValueError:
                continue
            if suffix.lower() == "k":
                value *= 1000
            elif suffix.lower() == "m":
                value *= 1_000_000
            values.append(value)
        if len(values) >= 2:
            minimum, maximum = values[0], values[1]
        elif values:
            minimum = maximum = values[0]
    currency = _clean(compensation.get("currency")).upper()[:8]
    return minimum, maximum, currency, summary[:200]


def normalize_job(raw: dict[str, Any], *, default_source: str = "") -> dict[str, Any]:
    """Convert one CLI (or board) job object into RecruiMate's job shape."""
    raw = raw or {}
    source = _clean(raw.get("source")) or _clean(default_source) or "unknown"
    title = _first([_clean(raw.get("title")), _clean(raw.get("job_title")), "Untitled role"])
    company = _first(
        [
            _clean(raw.get("employer")),
            _clean(raw.get("company")),
            _clean(raw.get("company_name")),
        ]
    )
    location = _first([_clean(raw.get("location")), _clean(raw.get("candidate_required_location"))])
    workplace = _clean(raw.get("workplace")).lower()
    remote_flag = raw.get("remote")
    if remote_flag is None:
        remote_flag = workplace == "remote"
    remote = bool(remote_flag)
    description = _clean(raw.get("description")) or _clean(raw.get("raw_text"))[:40000]
    tags = [str(t).strip() for t in (raw.get("tags") or []) if str(t).strip()]
    skills = extract_skills(f"{description} {', '.join(tags)}") if description else []
    for tag in tags:
        if tag and tag.lower() not in {s.lower() for s in skills} and len(skills) < 25:
            skills.append(tag)
    salary_min, salary_max, currency, salary_text = _salary(raw)
    if salary_min is None and raw.get("salary_min") is not None:
        try:
            salary_min = float(raw["salary_min"])
        except (TypeError, ValueError):
            salary_min = None
    if salary_max is None and raw.get("salary_max") is not None:
        try:
            salary_max = float(raw["salary_max"])
        except (TypeError, ValueError):
            salary_max = None
    currency = currency or _clean(raw.get("salary_currency")).upper()[:8]
    salary_text = salary_text or _clean(raw.get("salary_text"))[:200]
    external_id = _first(
        [_clean(raw.get("id")), _clean(raw.get("source_job_id")), _clean(raw.get("external_id"))]
    )
    # Re-normalising an already normalised row must keep its skills.
    if isinstance(raw.get("skills"), list):
        for skill in raw["skills"]:
            if isinstance(skill, str) and skill.strip() and skill not in skills:
                skills.append(skill.strip())
        skills = skills[:25]
    source_url = _first([_clean(raw.get("source_url")), _clean(raw.get("url"))])
    application = raw.get("application") if isinstance(raw.get("application"), dict) else {}
    apply_url = _first(
        [
            _clean(raw.get("application_url")),
            _clean(raw.get("apply_url")),
            _clean(application.get("url")),
            source_url,
        ]
    )
    posted_at = _parse_date(raw.get("posted_date") or raw.get("posted_at") or raw.get("date_posted"))
    level = _first([_clean(raw.get("level")), _clean(raw.get("experience_level"))])
    employment_type = _clean(raw.get("employment_type"))

    return {
        "title": title[:255],
        "company": company[:255],
        "location": location[:255],
        "remote": remote,
        "description": description[:40000],
        "skills": skills[:25],
        "tags": tags[:25],
        "employment_type": employment_type[:64],
        "experience_level": level[:64],
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_currency": currency,
        "salary_text": salary_text,
        "posted_at": posted_at,
        "source": source[:64],
        "source_job_id": external_id[:200],
        "source_url": source_url[:1024],
        "apply_url": apply_url[:1024],
        "dedupe_key": dedupe_key(title, company, location),
    }


def partition_jobs(payload: Any) -> list[dict[str, Any]]:
    """Flatten the CLI search envelope into a list of raw job objects.

    The CLI returns one partition per source; a partition may carry an error
    instead of jobs (e.g. Indeed without a market). Those are skipped.
    """
    jobs: list[dict[str, Any]] = []
    data = payload if isinstance(payload, dict) else {}
    partitions = data.get("partitions") or []
    for partition in partitions:
        if not isinstance(partition, dict):
            continue
        for job in partition.get("jobs") or []:
            if isinstance(job, dict):
                job.setdefault("source", partition.get("source", ""))
                jobs.append(job)
    if not jobs and isinstance(data.get("jobs"), list):
        jobs = [j for j in data["jobs"] if isinstance(j, dict)]
    return jobs


def partition_errors(payload: Any) -> list[dict[str, str]]:
    """Collect per-source errors from a search envelope."""
    errors: list[dict[str, str]] = []
    data = payload if isinstance(payload, dict) else {}
    for partition in data.get("partitions") or []:
        if not isinstance(partition, dict):
            continue
        error = partition.get("error")
        if isinstance(error, dict):
            errors.append(
                {
                    "source": str(partition.get("source", "unknown")),
                    "code": str(error.get("code", "ERROR")),
                    "message": str(error.get("message", ""))[:300],
                }
            )
    return errors
