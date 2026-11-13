"""Real job-board importers for the target job pool.

Server-side only, fixed hosts (no user-supplied URLs here, so no SSRF
surface). Two boards with public JSON APIs:

* **Remotive** — ``https://remotive.com/api/remote-jobs`` (supports a search
  term server-side).
* **RemoteOK** — ``https://remoteok.com/api`` (no server-side search; the
  query is applied client-side over position/tags).

Both return listings that are normalised into a shape ``save_postings`` can
write straight into ``job_postings``.

Tests inject a fake ``transport`` (an object with ``get``) instead of hitting
the network.
"""
from __future__ import annotations

import html
import json
import re

import httpx

SOURCES: tuple[str, ...] = ("remotive", "remoteok")
_TIMEOUT = 30.0
_UA = "RecruiMate/1.0 (candidate career coach; local app)"


class ImportError(Exception):
    """Raised when a board is unreachable or returns unusable data."""


def strip_html(markup: str) -> str:
    """HTML → readable text."""
    text = re.sub(r"<\s*br\s*/?>", "\n", markup or "", flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"[ \t]+", " ", text).strip()


def min_years_from(text: str) -> float:
    """Extract a minimum-experience hint like ``3+ years``."""
    match = re.search(r"(\d+)\s*\+?\s*(?:\(|)?\s*years", text or "", re.IGNORECASE)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return 0.0
    return 0.0


def _norm_remotive(job: dict) -> dict | None:
    title = (job.get("title") or "").strip()
    url = (job.get("url") or "").strip()
    if not title or not url:
        return None
    description = strip_html(job.get("description") or "")
    tags = [str(t).strip() for t in (job.get("tags") or []) if str(t).strip()]
    return {
        "title": title[:255],
        "company": (job.get("company_name") or "").strip()[:255],
        "location": (job.get("candidate_required_location") or "").strip()[:255],
        "url": url[:1024],
        "source": "remotive",
        "tags": tags,
        "raw_text": (
            f"Title: {title}\n"
            f"Company: {job.get('company_name', '')}\n"
            f"Location: {job.get('candidate_required_location', '')}\n"
            f"Employment type: {job.get('job_type', '')}\n"
            f"Tags: {', '.join(tags)}\n"
            f"Description: {description[:8000]}\n"
        ),
        "description": description,
    }


def _norm_remoteok(job: dict) -> dict | None:
    if not isinstance(job, dict) or "position" not in job:
        return None  # first element is a legal notice; skip non-listing rows
    title = (job.get("position") or "").strip()
    url = (job.get("url") or job.get("apply_url") or "").strip()
    if not title or not url:
        return None
    description = strip_html(job.get("description") or "")
    tags = [str(t).strip() for t in (job.get("tags") or []) if str(t).strip()]
    location = str(job.get("location") or "").strip()
    salary_min, salary_max = job.get("salary_min"), job.get("salary_max")
    if salary_min or salary_max:
        location = f"{location} (${salary_min or '?'}-${salary_max or '?'})".strip()
    return {
        "title": title[:255],
        "company": (job.get("company") or "").strip()[:255],
        "location": location[:255],
        "url": url[:1024],
        "source": "remoteok",
        "tags": tags,
        "raw_text": (
            f"Title: {title}\n"
            f"Company: {job.get('company', '')}\n"
            f"Location: {location}\n"
            f"Tags: {', '.join(tags)}\n"
            f"Description: {description[:8000]}\n"
        ),
        "description": description,
    }


async def fetch_postings(
    source: str, query: str = "", limit: int = 12, transport=None
) -> list[dict]:
    """Fetch and normalise ``limit`` postings from ``source``.

    ``transport`` lets tests inject a fake httpx client. Raises
    :class:`ImportError` with a human-readable message on failure.
    """
    source = (source or "").strip().lower()
    if source not in SOURCES:
        raise ValueError(f"Unknown job source '{source}'. Choose one of: {', '.join(SOURCES)}.")
    limit = max(1, min(int(limit), 50))
    query = (query or "").strip()
    client = transport or httpx.AsyncClient(
        timeout=_TIMEOUT, headers={"User-Agent": _UA}, follow_redirects=True
    )
    try:
        try:
            if source == "remotive":
                response = await client.get(
                    "https://remotive.com/api/remote-jobs",
                    params={"limit": max(limit * 3, 30), **({"search": query} if query else {})},
                )
                response.raise_for_status()
                payload = response.json()
                rows = payload.get("jobs") or []
                normalised = [p for p in (_norm_remotive(r) for r in rows) if p]
                if query:
                    lowered = query.lower()
                    normalised = [
                        p
                        for p in normalised
                        if lowered in p["title"].lower()
                        or lowered in p["description"].lower()
                        or any(lowered in t.lower() for t in p["tags"])
                    ]
            else:  # remoteok
                response = await client.get("https://remoteok.com/api")
                response.raise_for_status()
                rows = response.json()
                if isinstance(rows, str):  # some deployments prepend a guard string
                    rows = json.loads(rows)
                normalised = [p for p in (_norm_remoteok(r) for r in rows) if p]
                if query:
                    lowered = query.lower()
                    normalised = [
                        p
                        for p in normalised
                        if lowered in p["title"].lower()
                        or lowered in p["company"].lower()
                        or any(lowered in t.lower() for t in p["tags"])
                    ]
        except httpx.HTTPError as exc:
            raise ImportError(f"Could not reach {source}: {exc}") from exc
        except (ValueError, KeyError, TypeError) as exc:
            raise ImportError(f"{source} returned unexpected data: {exc}") from exc

        if not normalised:
            raise ImportError(
                f"No postings matched '{query}' on {source}. Try a broader term."
                if query
                else f"{source} returned no postings right now."
            )
        return normalised[:limit]
    finally:
        if transport is None:
            await client.aclose()
