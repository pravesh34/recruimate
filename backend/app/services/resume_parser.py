"""Resume file parsing and offline profile extraction."""
from __future__ import annotations

import io
import re
from datetime import datetime

from ..schemas import (
    CandidateProfile,
    EducationItem,
    ExperienceItem,
    ProjectItem,
)
from .skills import SOFT_SKILLS, extract_skills

SECTION_HEADINGS = {
    "summary": ["summary", "professional summary", "profile", "objective", "about me", "about"],
    "skills": ["skills", "technical skills", "core competencies", "technologies", "tech stack", "expertise"],
    "experience": ["experience", "work experience", "professional experience", "employment", "work history", "internships"],
    "education": ["education", "academic background", "academics", "qualifications"],
    "projects": ["projects", "personal projects", "academic projects", "selected projects", "key projects"],
    "certifications": ["certifications", "certificates", "licenses", "courses"],
    "achievements": ["achievements", "awards", "honors", "honours", "accomplishments"],
}

DATE_RANGE_RE = re.compile(
    r"((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*)?"
    r"((?:19|20)\d{2})\s*[-–—to]+\s*"
    r"(?:(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*)?"
    r"((?:19|20)\d{2}|present|current|ongoing)",
    re.I,
)
BULLET_RE = re.compile(r"^\s*(?:[-•▪◦*·‣]|\d+[.)])\s*")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{3,5}\)?[\s.-]?)\d{3,5}[\s.-]?\d{3,5}")
URL_RE = re.compile(r"https?://\S+|(?:www\.|github\.com|linkedin\.com)\S+", re.I)


class ResumeParseError(ValueError):
    pass


def extract_text(filename: str, data: bytes) -> str:
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if suffix == "pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:  # pragma: no cover
            raise ResumeParseError("PDF support is not installed") from exc
        try:
            reader = PdfReader(io.BytesIO(data))
            pages = [page.extract_text() or "" for page in reader.pages]
        except Exception as exc:
            raise ResumeParseError(f"Could not read this PDF: {exc}") from exc
        text = "\n".join(pages)
    elif suffix in {"txt", "md"}:
        text = data.decode("utf-8", errors="replace")
    elif suffix == "docx":
        try:
            import docx  # type: ignore
        except ImportError as exc:
            raise ResumeParseError("DOCX support requires python-docx") from exc
        try:
            document = docx.Document(io.BytesIO(data))
            text = "\n".join(p.text for p in document.paragraphs)
        except Exception as exc:
            raise ResumeParseError(f"Could not read this DOCX: {exc}") from exc
    else:
        raise ResumeParseError("Unsupported file type. Upload a PDF, DOCX or TXT resume.")
    text = clean_text(text)
    if len(text.strip()) < 40:
        raise ResumeParseError(
            "No readable text was found. The PDF may be scanned; upload a text-based version."
        )
    return text


def clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _heading_key(line: str) -> str | None:
    stripped = line.strip().strip(":").strip()
    if not stripped or len(stripped) > 60:
        return None
    normalized = re.sub(r"[^a-z ]", "", stripped.lower()).strip()
    for key, variants in SECTION_HEADINGS.items():
        if normalized in variants:
            return key
    return None


def split_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {"header": []}
    current = "header"
    for line in text.splitlines():
        key = _heading_key(line)
        if key:
            current = key
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return {k: "\n".join(v).strip() for k, v in sections.items()}


def _bullets(section: str) -> list[str]:
    items: list[str] = []
    for raw in section.splitlines():
        line = raw.strip()
        if not line:
            continue
        cleaned = BULLET_RE.sub("", line).strip()
        if cleaned:
            items.append(cleaned)
    return items


def _parse_name(header: str) -> str:
    for line in header.splitlines()[:6]:
        candidate = line.strip()
        if not candidate or len(candidate) > 50:
            continue
        if EMAIL_RE.search(candidate) or URL_RE.search(candidate) or any(ch.isdigit() for ch in candidate):
            continue
        lower = candidate.lower()
        if any(word in lower for word in ("resume", "curriculum", "vitae", "cv", "phone", "email")):
            continue
        words = candidate.split()
        if 1 < len(words) <= 5 and all(re.match(r"^[A-Za-z][A-Za-z.'-]*$", w) for w in words):
            return candidate
    return ""


def _parse_month(text: str | None, default_year: int | None = None) -> int:
    if not text:
        return 1
    months = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
    match = re.match(r"([a-z]{3})", text.lower())
    if match and match.group(1) in months:
        return months.index(match.group(1)) + 1
    return default_year or 1


def _months_between(start_year: int, start_month: int, end_year: int, end_month: int) -> int:
    return max(0, (end_year - start_year) * 12 + (end_month - start_month))


def estimate_years_experience(experience_text: str, full_text: str) -> float:
    now = datetime.now()
    total_months = 0
    for match in DATE_RANGE_RE.finditer(experience_text or ""):
        start_month = _parse_month(match.group(1))
        start_year = int(match.group(2))
        end_raw = match.group(3).lower()
        if end_raw in ("present", "current", "ongoing"):
            end_year, end_month = now.year, now.month
        else:
            end_year, end_month = int(end_raw), 12
        total_months += _months_between(start_year, start_month, end_year, end_month)
    if total_months:
        return round(min(total_months / 12, 40), 1)
    explicit = re.search(r"(\d+(?:\.\d+)?)\s*\+?\s*years?", full_text or "", re.I)
    if explicit:
        return min(float(explicit.group(1)), 40)
    return 0.0


def _parse_experience(section: str) -> list[ExperienceItem]:
    if not section.strip():
        return []
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in section.splitlines():
        if DATE_RANGE_RE.search(line) and current:
            blocks.append(current)
            current = [line]
        elif not line.strip() and current and len(current) > 2:
            blocks.append(current)
            current = []
        elif line.strip():
            current.append(line)
    if current:
        blocks.append(current)

    items: list[ExperienceItem] = []
    for block in blocks[:8]:
        text = " ".join(block).strip()
        if len(text) < 10:
            continue
        head = block[0].strip()
        date_match = DATE_RANGE_RE.search(head) or DATE_RANGE_RE.search(text)
        dates = date_match.group(0) if date_match else ""
        head_clean = BULLET_RE.sub("", head)
        head_clean = DATE_RANGE_RE.sub("", head_clean).strip(" |,–—-·")
        company = ""
        title = ""
        if " at " in head_clean.lower():
            idx = head_clean.lower().index(" at ")
            title, company = head_clean[:idx].strip(), head_clean[idx + 4 :].strip()
        elif "|" in head_clean:
            parts = [p.strip() for p in head_clean.split("|") if p.strip()]
            title = parts[0]
            company = parts[1] if len(parts) > 1 else ""
        else:
            title = head_clean
        highlights = [
            BULLET_RE.sub("", line).strip()
            for line in block[1:]
            if line.strip() and not DATE_RANGE_RE.search(line)
        ][:6]
        items.append(
            ExperienceItem(
                title=title[:160],
                company=company[:160],
                start=dates,
                description=" ".join(highlights)[:1200],
                highlights=highlights,
            )
        )
    return items


def _parse_education(section: str) -> list[EducationItem]:
    if not section.strip():
        return []
    degree_re = re.compile(
        r"(bachelor|master|b\.?tech|m\.?tech|b\.?e\.?|m\.?e\.?|b\.?sc|m\.?sc|mba|ph\.?d|diploma|associate|high school)",
        re.I,
    )
    items: list[EducationItem] = []
    for block in re.split(r"\n\s*\n", section):
        text = " ".join(line.strip() for line in block.splitlines() if line.strip())
        if not text:
            continue
        match = degree_re.search(text)
        dates = DATE_RANGE_RE.search(text)
        items.append(
            EducationItem(
                degree=match.group(0) if match else text[:80],
                institution=text[:180] if not match else text[match.end() :].strip(" ,|–—-")[:160],
                start_year=dates.group(2) if dates else "",
                end_year=(dates.group(3) if dates and dates.group(3).lower() not in ("present", "current", "ongoing") else "") if dates else "",
                details=text[:400],
            )
        )
    return items[:5]


def _parse_projects(section: str) -> list[ProjectItem]:
    if not section.strip():
        return []
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in section.splitlines():
        if not line.strip():
            if current:
                blocks.append(current)
                current = []
            continue
        if BULLET_RE.match(line) and len(line.strip()) < 90 and current:
            blocks.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        blocks.append(current)

    projects: list[ProjectItem] = []
    for block in blocks[:8]:
        lines = [BULLET_RE.sub("", line).strip() for line in block if line.strip()]
        if not lines:
            continue
        name = lines[0][:120]
        description = " ".join(lines[1:] or lines)[:800]
        techs = extract_skills(" ".join(lines))
        projects.append(ProjectItem(name=name, description=description, technologies=techs))
    return projects


def _parse_simple_list(section: str) -> list[str]:
    items = _bullets(section)
    if len(items) == 1 and "," in items[0]:
        items = [x.strip() for x in items[0].split(",") if x.strip()]
    return [i[:240] for i in items][:20]


def _split_skills(section: str) -> list[str]:
    if not section:
        return []
    tokens = re.split(r"[,|•·/;\n\t]+", section)
    cleaned = [t.strip(" -–—") for t in tokens if t.strip()]
    useful = [t for t in cleaned if 1 < len(t) <= 40]
    return useful


def heuristic_resume_profile(text: str) -> CandidateProfile:
    text = clean_text(text)
    sections = split_sections(text)
    header = sections.get("header", "")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    name = _parse_name(header) or _parse_name(text[:300]) or (lines[0] if lines else "")
    email_match = EMAIL_RE.search(header) or EMAIL_RE.search(text)
    phone_match = PHONE_RE.search(header)
    urls = URL_RE.findall(header) or URL_RE.findall(text[:800])
    location = ""
    for line in header.splitlines():
        if "location" in line.lower() and ":" in line:
            location = line.split(":", 1)[1].strip()[:80]

    skills_text = sections.get("skills", "")
    all_skills = extract_skills(text)
    listed = extract_skills(skills_text)
    # keep taxonomy order but prioritise skills explicitly listed in the skills section
    skills = listed + [s for s in all_skills if s not in listed]
    soft = [s for s in skills if s in SOFT_SKILLS]
    technical = [s for s in skills if s not in SOFT_SKILLS]

    experience = _parse_experience(sections.get("experience", ""))
    education = _parse_education(sections.get("education", ""))
    projects = _parse_projects(sections.get("projects", ""))
    certifications = _parse_simple_list(sections.get("certifications", ""))
    achievements = _parse_simple_list(sections.get("achievements", ""))
    summary = sections.get("summary", "")[:1200]
    if not summary:
        non_heading = [
            ln for ln in lines[1:8]
            if not EMAIL_RE.search(ln) and not URL_RE.search(ln) and len(ln) > 40
        ]
        summary = non_heading[0][:600] if non_heading else ""

    years = estimate_years_experience(sections.get("experience", ""), text)
    profile = CandidateProfile(
        name=name[:120],
        headline=(experience[0].title if experience else (education[0].degree if education else ""))[:160],
        email=email_match.group(0) if email_match else "",
        phone=phone_match.group(0).strip() if phone_match else "",
        location=location,
        summary=summary,
        skills=technical,
        soft_skills=soft,
        education=education,
        experience=experience,
        projects=projects,
        certifications=certifications,
        achievements=achievements,
        years_experience=years,
    )
    profile.resume_strengths, profile.resume_weaknesses, profile.improvement_suggestions = _review(
        text, profile, bool(skills_text), urls
    )
    missing = []
    if not profile.email:
        missing.append("email")
    if not profile.phone:
        missing.append("phone")
    if not profile.summary:
        missing.append("summary")
    if not profile.education:
        missing.append("education")
    if not profile.experience:
        missing.append("experience")
    if not profile.projects:
        missing.append("projects")
    if not profile.skills:
        missing.append("skills")
    profile.unknown_fields = missing
    return profile


def _review(text: str, profile: CandidateProfile, has_skills_heading: bool, urls: list[str]):
    strengths: list[str] = []
    weaknesses: list[str] = []
    suggestions: list[str] = []
    lower = text.lower()

    if profile.projects:
        strengths.append(f"Includes {len(profile.projects)} project(s), giving interviewers concrete work to probe.")
    if profile.experience:
        strengths.append(f"Shows {len(profile.experience)} experience entr{'y' if len(profile.experience) == 1 else 'ies'} with a timeline.")
    if len(profile.skills) >= 8:
        strengths.append(f"Lists {len(profile.skills)} recognisable technical skills.")
    if re.search(r"\b\d+(?:\.\d+)?\s*(?:%|x|k|m|users|customers|ms|seconds|hours)\b", lower):
        strengths.append("Contains quantified impact, which makes achievements credible.")
    if profile.certifications:
        strengths.append("Certifications are called out explicitly.")
    if urls:
        strengths.append("Includes professional links (portfolio, GitHub or LinkedIn).")

    if len(text) < 700:
        weaknesses.append("The resume is very short, leaving room for ambiguity about your impact.")
        suggestions.append("Expand each project with the problem, your actions, the result and the tools used.")
    if not profile.email or not profile.phone:
        weaknesses.append("Contact details are incomplete or hard to parse.")
        suggestions.append("Add a clear email and phone number at the top of the resume.")
    if not urls:
        weaknesses.append("No portfolio, GitHub or LinkedIn link was detected.")
        suggestions.append("Add a GitHub or portfolio link so reviewers can verify your work.")
    if not has_skills_heading:
        weaknesses.append("No dedicated skills section was detected.")
        suggestions.append("Create a 'Technical Skills' section grouped by language, framework, database and tool.")
    if not profile.projects:
        weaknesses.append("No projects were detected, which is a major gap for entry-level roles.")
        suggestions.append("Add 2–3 projects with the stack, your specific contribution and a measurable outcome.")
    if not profile.experience:
        weaknesses.append("No work or internship experience was detected.")
        suggestions.append("Add internships, freelance work or open-source contributions; label them honestly.")
    if len(profile.skills) < 6:
        weaknesses.append("Few recognised technical skills were found.")
        suggestions.append("Name the specific tools you use (for example PostgreSQL, Docker, React) rather than only saying 'programming'.")
    if not re.search(r"\b\d+(?:\.\d+)?\s*(?:%|x|k|m|users|customers|ms|seconds|hours)\b", lower):
        weaknesses.append("Achievements are not quantified.")
        suggestions.append("Add numbers: latency reduced by 30%, 500 users onboarded, 12k records processed.")
    if not profile.summary or len(profile.summary) < 50:
        weaknesses.append("The professional summary is missing or too thin.")
        suggestions.append("Write a 2–3 line summary naming your target role, strongest skills and one proof point.")
    generic = sum(lower.count(phrase) for phrase in ("hardworking", "team player", "passionate", "detail-oriented", "go-getter"))
    if generic >= 2:
        weaknesses.append("Generic self-descriptions appear more than once.")
        suggestions.append("Replace adjectives with evidence: what did you build, improve or measure?")
    if lower.count("responsible for") >= 2:
        weaknesses.append("Several bullets use 'responsible for' instead of describing outcomes.")
        suggestions.append("Start bullets with action verbs and end with impact (Built, Reduced, Automated, Led).")
    if profile.experience and not DATE_RANGE_RE.search(profile.experience[0].start):
        weaknesses.append("Experience dates are missing or ambiguous.")
        suggestions.append("Use consistent month/year ranges (for example Jan 2024 – Present).")
    if not profile.education:
        weaknesses.append("Education details are missing or not machine-readable.")
        suggestions.append("Add degree, institution and graduation year in a dedicated Education section.")
    if len(weaknesses) < 2:
        weaknesses.append("Some bullet points describe duties rather than measurable results.")
        suggestions.append("Rewrite the three weakest bullets using the action → tool → result pattern.")

    return strengths, weaknesses[:8], suggestions[:8]
