"""Offline job-description parsing."""
from __future__ import annotations

import re

from ..schemas import JobProfile
from .skills import SOFT_SKILLS, detect_role_category, extract_skills

PREFERRED_HINTS = ("preferred", "nice to have", "nice-to-have", "bonus", "plus", "desirable", "advantage")
BULLET_RE = re.compile(r"^\s*(?:[-•▪◦*·‣]|\d+[.)])\s*")
YEAR_RE = re.compile(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:-\s*\d+\s*)?years?", re.I)
DEGREE_RE = re.compile(r"(bachelor'?s?|master'?s?|b\.?tech|m\.?tech|b\.?e\b|m\.?e\b|b\.?sc|m\.?sc|mba|ph\.?d|degree)", re.I)


def _lines(text: str) -> list[str]:
    return [ln.strip() for ln in (text or "").splitlines() if ln.strip()]


def _find_heading_index(lines: list[str], keywords: tuple[str, ...]) -> int | None:
    for i, line in enumerate(lines):
        normalized = re.sub(r"[^a-z ]", "", line.lower()).strip()
        if len(normalized) <= 50 and any(k in normalized for k in keywords):
            return i
    return None


def _section_text(lines: list[str], start: int, stop_keywords: tuple[str, ...]) -> str:
    collected: list[str] = []
    for line in lines[start + 1 :]:
        normalized = re.sub(r"[^a-z ]", "", line.lower()).strip()
        if len(normalized) <= 50 and any(k in normalized for k in stop_keywords):
            break
        collected.append(line)
    return "\n".join(collected)


def heuristic_job_profile(text: str, source_url: str = "") -> JobProfile:
    text = (text or "").strip()
    lines = _lines(text)
    title = ""
    for line in lines[:6]:
        cleaned = re.sub(r"^(job title|role|position)\s*[:\-]\s*", "", line, flags=re.I).strip()
        if 3 <= len(cleaned) <= 90 and not cleaned.lower().startswith(("about", "we ", "company")):
            title = cleaned
            break
    title_match = re.search(r"(?:job title|position|role)\s*[:\-]\s*(.+)", text, re.I)
    if title_match:
        title = title_match.group(1).strip()[:120]

    company = ""
    company_match = re.search(r"(?:company|organisation|organization|employer)\s*[:\-]\s*(.+)", text, re.I)
    if company_match:
        company = company_match.group(1).strip().splitlines()[0][:120]
    else:
        at_match = re.search(r"\bat\s+([A-Z][\w&.\- ]{2,60})(?:\s*[|\-–—]|\n|$)", text)
        if at_match:
            company = at_match.group(1).strip()[:120]

    location = ""
    loc_match = re.search(r"(?:location|based in)\s*[:\-]\s*(.+)", text, re.I)
    if loc_match:
        location = loc_match.group(1).strip().splitlines()[0][:120]

    employment = ""
    for option in ("full-time", "part-time", "internship", "contract", "remote", "hybrid"):
        if option in text.lower():
            employment = option
            break

    preferred_context: list[str] = []
    for i, line in enumerate(lines):
        if any(hint in line.lower() for hint in PREFERRED_HINTS):
            preferred_context.append(line)
            if i + 1 < len(lines):
                preferred_context.append(lines[i + 1])
    preferred_skills = [s for s in extract_skills("\n".join(preferred_context)) if s not in SOFT_SKILLS]
    all_skills = extract_skills(text)
    required_skills = [s for s in all_skills if s not in preferred_skills]
    soft = [s for s in all_skills if s in SOFT_SKILLS]

    resp_idx = _find_heading_index(lines, ("responsibilities", "what you will do", "the role", "duties", "you will"))
    if resp_idx is not None:
        resp_text = _section_text(
            lines,
            resp_idx,
            ("requirements", "qualifications", "benefits", "about us", "nice to have", "skills"),
        )
        responsibilities = [
            BULLET_RE.sub("", ln).strip() for ln in _lines(resp_text)
        ]
    else:
        responsibilities = [
            BULLET_RE.sub("", ln).strip() for ln in lines if BULLET_RE.match(ln)
        ]
    responsibilities = [r[:300] for r in responsibilities if len(r) > 15][:10]

    min_years = 0.0
    year_matches = [float(m.group(1)) for m in YEAR_RE.finditer(text) if float(m.group(1)) < 25]
    if year_matches:
        min_years = min(year_matches)

    education_requirements = []
    for line in lines:
        if DEGREE_RE.search(line) and len(line) < 240:
            education_requirements.append(line[:240])
    education_requirements = list(dict.fromkeys(education_requirements))[:5]

    certs = []
    for line in lines:
        if re.search(r"certif", line, re.I) and len(line) < 200:
            certs.append(BULLET_RE.sub("", line).strip()[:200])
    certs = list(dict.fromkeys(certs))[:5]

    behavioural = []
    for skill in soft:
        behavioural.append(f"Demonstrates {skill.lower()} in a professional context.")

    category = detect_role_category(title, text)

    if not title:
        title = {
            "ai_ml": "AI / Machine Learning role",
            "data": "Data role",
            "frontend": "Frontend role",
            "backend": "Backend role",
            "fullstack": "Full-stack role",
            "mobile": "Mobile role",
            "devops": "DevOps role",
            "security": "Security role",
            "design": "Design role",
            "qa": "QA role",
            "product": "Product role",
        }.get(category, "Role")

    return JobProfile(
        job_title=title[:160],
        company=company,
        location=location,
        employment_type=employment,
        role_category=category,
        required_skills=required_skills[:30],
        preferred_skills=preferred_skills[:20],
        experience_requirements=[f"{min_years:g}+ years of relevant experience"] if min_years else [],
        education_requirements=education_requirements,
        responsibilities=responsibilities,
        behavioural_expectations=behavioural[:8],
        certifications=certs,
        min_years_experience=min_years,
    )
