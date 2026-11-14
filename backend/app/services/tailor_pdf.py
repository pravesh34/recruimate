"""Two-variant PDF resumes for a pool job.

``asis``  — the candidate's real profile, reordered to lead with the evidence
            that matters for the target job. Nothing is invented.
``dream`` — a clearly-labelled development target: what the candidate's
            résumé would look like once they close the job's skill gaps.
            Missing skills are marked as goals with a concrete project idea
            each, so the document doubles as a work plan. It never claims
            experience the candidate does not have.

Both render as clean, ATS-friendly PDFs via reportlab (deterministic,
no network, no external assets).
"""
from __future__ import annotations

from io import BytesIO
from typing import Any

from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .tailor_service import tailor_for_job

_ACCENT = "#1d4ed8"      # brand-ish blue for headings/rules
_SOFT = "#6b7280"        # muted grey
_GOAL = "#b45309"        # amber for dream-variant goal markers


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "name": ParagraphStyle(
            "Name", parent=base["Title"], fontName="Helvetica-Bold",
            fontSize=20, leading=24, alignment=TA_CENTER, textColor="#111827", spaceAfter=2,
        ),
        "contact": ParagraphStyle(
            "Contact", parent=base["Normal"], fontName="Helvetica",
            fontSize=9.5, leading=13, alignment=TA_CENTER, textColor=_SOFT, spaceAfter=4,
        ),
        "banner": ParagraphStyle(
            "Banner", parent=base["Normal"], fontName="Helvetica-Oblique",
            fontSize=9, leading=12.5, alignment=TA_CENTER, textColor=_GOAL, spaceAfter=6,
        ),
        "section": ParagraphStyle(
            "Section", parent=base["Heading2"], fontName="Helvetica-Bold",
            fontSize=11.5, leading=15, textColor=_ACCENT, spaceBefore=10, spaceAfter=3,
        ),
        "role": ParagraphStyle(
            "Role", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=10.5, leading=14, textColor="#111827",
        ),
        "meta": ParagraphStyle(
            "Meta", parent=base["Normal"], fontName="Helvetica",
            fontSize=9, leading=12, textColor=_SOFT, spaceAfter=2,
        ),
        "body": ParagraphStyle(
            "Body", parent=base["Normal"], fontName="Helvetica",
            fontSize=9.5, leading=13.5, textColor="#1f2937", spaceAfter=3,
        ),
        "bullet": ParagraphStyle(
            "Bullet", parent=base["Normal"], fontName="Helvetica",
            fontSize=9.5, leading=13, textColor="#1f2937",
        ),
        "note": ParagraphStyle(
            "Note", parent=base["Normal"], fontName="Helvetica-Oblique",
            fontSize=8, leading=11, alignment=TA_CENTER, textColor=_SOFT, spaceBefore=8,
        ),
    }


def _esc(text: Any) -> str:
    out = str(text or "")
    return (
        out.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


def _bullets(items: list[str], style_key: str = "bullet") -> ListFlowable:
    styles = _styles()
    return ListFlowable(
        [ListItem(Paragraph(_esc(t), styles[style_key]), leftIndent=14) for t in items],
        bulletType="bullet",
        start="•",
        leftIndent=10,
    )


def _header(story: list, candidate, job: dict, variant: str, styles: dict) -> None:
    name = candidate.name or "Candidate"
    story.append(Paragraph(_esc(name), styles["name"]))
    contact_bits = [candidate.email, candidate.phone, candidate.location]
    headline = candidate.headline or candidate.summary
    if headline:
        subtitle = headline if len(headline) <= 120 else headline[:117] + "…"
        if variant == "dream":
            subtitle = f"Target profile — {job.get('title') or 'the role'}"
        story.append(Paragraph(_esc(subtitle), styles["contact"]))
    line = "  ·  ".join(_esc(b) for b in contact_bits if b)
    if line:
        story.append(Paragraph(line, styles["contact"]))
    story.append(HRFlowable(width="100%", thickness=1.2, color=_ACCENT, spaceAfter=8))


def _section(story: list, title: str) -> None:
    story.append(Paragraph(_esc(title.upper()), _styles()["section"]))
    story.append(HRFlowable(width="100%", thickness=0.6, color="#dbeafe", spaceAfter=5))


def build_asis_resume(candidate, tailor: dict, job: dict) -> bytes:
    """The candidate's real résumé, ordered to lead with job-relevant evidence."""
    styles = _styles()
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, topMargin=14 * mm, bottomMargin=14 * mm,
        leftMargin=16 * mm, rightMargin=16 * mm, title=f"Resume — {job.get('title', '')}",
    )
    story: list = []
    _header(story, candidate, job, "asis", styles)

    matched = tailor.get("summary", {}).get("matched_skills", [])
    if matched:
        _section(story, "Highlights")
        story.append(
            Paragraph(
                f"Strong fit areas for this role: <b>{_esc(', '.join(matched[:6]))}</b>.",
                styles["body"],
            )
        )

    if candidate.skills:
        _section(story, "Skills")
        story.append(Paragraph(_esc(", ".join(candidate.skills[:30])), styles["body"]))

    if candidate.experience:
        _section(story, "Experience")
        ranked = {b["text"]: b for b in tailor.get("bullets", [])}
        for item in candidate.experience:
            role = item.title or "Role"
            company = item.company
            period = " – ".join(x for x in [item.start, item.end] if x)
            story.append(Paragraph(f"{_esc(role)}{_esc(' — ' + company if company else '')}", styles["role"]))
            if period:
                story.append(Paragraph(_esc(period), styles["meta"]))
            bullets = list(item.highlights or [])
            if not bullets and item.description:
                bullets = [s.strip() for s in item.description.replace("\n", ". ").split(".") if s.strip()][:6]
            # Job-relevant bullets first, keeping the candidate's own wording.
            bullets.sort(key=lambda b: 0 if b in ranked else 1)
            if bullets:
                story.append(_bullets(bullets[:6]))
            story.append(Spacer(1, 4))

    if candidate.projects:
        _section(story, "Projects")
        for item in candidate.projects[:4]:
            story.append(Paragraph(_esc(item.name or "Project"), styles["role"]))
            desc = (item.description or "").strip()
            if desc and desc.lower() != (item.name or "").strip().lower():
                story.append(Paragraph(_esc(desc), styles["body"]))
            if item.technologies:
                story.append(Paragraph(_esc("Tech: " + ", ".join(item.technologies[:8])), styles["meta"]))
            story.append(Spacer(1, 3))

    if candidate.education:
        _section(story, "Education")
        for item in candidate.education:
            line = " — ".join(x for x in [_esc(item.degree), _esc(item.institution)] if x)
            if item.field:
                line += f", {_esc(item.field)}"
            if item.end_year:
                line += f" ({_esc(item.end_year)})"
            story.append(Paragraph(line, styles["body"]))
            details = (item.details or "").strip()
            line_words = set(line.lower().replace("—", " ").replace(",", " ").split())
            detail_words = set(details.lower().replace("—", " ").replace(",", " ").split())
            overlap = len(line_words & detail_words) / max(1, len(detail_words))
            if details and overlap < 0.7:
                story.append(Paragraph(_esc(details), styles["meta"]))

    if candidate.certifications:
        _section(story, "Certifications")
        story.append(_bullets(candidate.certifications[:6]))

    doc.build(story)
    return buf.getvalue()


# Small library of concrete project ideas per common skill family.
_PROJECT_IDEAS = {
    "python": "Build a small CLI or API tool in Python and publish the repo with a README.",
    "javascript": "Build an interactive browser app (vanilla JS or React) and deploy it.",
    "typescript": "Migrate a small project to TypeScript and document the type decisions.",
    "react": "Build a React front-end for an existing API with routing and state.",
    "sql": "Model a small dataset, write analytical SQL, and document the queries.",
    "docker": "Containerise an existing project with a multi-stage Dockerfile.",
    "aws": "Deploy a personal project on AWS free tier (S3 + Lambda or similar).",
    "kubernetes": "Run a containerised project locally in k8s (minikube) with 2 services.",
    "java": "Build a small Spring Boot service with tests and document the design.",
    "go": "Build a small concurrency-focused Go tool and document the design.",
    "c++": "Build a small performance-focused C++ utility with a benchmark write-up.",
    "c#": "Build a small ASP.NET Core API and document the architecture.",
    ".net": "Build a small ASP.NET Core API and document the architecture.",
    "android": "Build a small Android app that solves one daily problem and publish it.",
    "ios": "Build a small SwiftUI app with persistence and publish it.",
    "php": "Build a small Laravel or plain-PHP CRUD app and document it.",
    "ruby": "Build a small Rails app and document the design choices.",
    "golang": "Build a small concurrency-focused Go tool and document the design.",
    "rust": "Build a small Rust CLI and write up ownership/borrow decisions.",
    "ml": "Train and evaluate a model on a public dataset; document the metrics.",
    "machine learning": "Train and evaluate a model on a public dataset; document the metrics.",
    "data science": "Run an end-to-end analysis (clean, model, visualise) on open data.",
    "insurance": "Do a domain deep-dive and write a one-page glossary of the domain.",
    "cloud": "Deploy a personal project to a cloud free tier and document the setup.",
    "devops": "Set up CI/CD for a personal project and document the pipeline.",
    "git": "Use feature-branch flow with PRs on a personal project for two weeks.",
}


def _idea_for(skill: str) -> str:
    key = skill.strip().lower()
    for known, idea in _PROJECT_IDEAS.items():
        if known in key:
            return idea
    return f"Build a small end-to-end artefact that uses {skill.strip()} and document the trade-offs out loud."


def build_dream_resume(candidate, tailor: dict, job: dict) -> bytes:
    """The development-target résumé: have-today vs building-next, clearly labelled."""
    styles = _styles()
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, topMargin=14 * mm, bottomMargin=14 * mm,
        leftMargin=16 * mm, rightMargin=16 * mm,
        title=f"Dream resume — {job.get('title', '')}",
    )
    story: list = []
    _header(story, candidate, job, "dream", styles)

    matched: list[str] = tailor.get("summary", {}).get("matched_skills", [])
    missing: list[str] = tailor.get("summary", {}).get("missing_skills", [])

    story.append(
        Paragraph(
            "This is a development target, not a factual résumé. Items marked ◆ are goals to "
            "build — work through them and this becomes your real, strong fit for "
            f"{_esc(job.get('title') or 'this role')}.",
            styles["banner"],
        )
    )
    story.append(HRFlowable(width="100%", thickness=0.6, color=_GOAL, spaceAfter=6))

    # Have today
    _section(story, "Have today")
    years = tailor.get("summary", {}).get("years_experience")
    have_bits = []
    if years:
        have_bits.append(f"{years:g} years of experience")
    if matched:
        have_bits.append("strong in " + ", ".join(matched[:6]))
    elif candidate.skills:
        have_bits.append("strong in " + ", ".join(candidate.skills[:6]))
    story.append(Paragraph(_esc(" · ".join(have_bits)) + ".", styles["body"]))
    top = [b["text"] for b in tailor.get("bullets", []) if b.get("matched_skills")][:3]
    if not top:
        top = [b["text"] for b in tailor.get("bullets", [])[:3]]
    if top:
        story.append(_bullets(top))
    story.append(Spacer(1, 4))

    # Building next — each missing skill as a goal with a concrete project idea
    if missing:
        _section(story, "Building next")
        rows = [[Paragraph("◆", ParagraphStyle("g", parent=styles["bullet"], textColor=_GOAL, alignment=TA_CENTER)),
                 Paragraph(f"<b>{_esc(skill)}</b>", styles["bullet"]),
                 Paragraph(_esc(_idea_for(skill)), styles["bullet"])]
                for skill in missing[:6]]
        table = Table(rows, colWidths=[8 * mm, 42 * mm, None])
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [None, "#fffbeb"]),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("LINEBELOW", (0, 0), (-1, -2), 0.4, "#fde68a"),
        ]))
        story.append(table)
        story.append(Spacer(1, 4))

    # Projected profile — the skills line they are working towards (case-deduped)
    _section(story, "Projected profile")
    seen: set[str] = set()
    projected: list[str] = []
    for skill in list(candidate.skills or [])[:10] + matched + missing[:6]:
        key = skill.strip().lower()
        if skill.strip() and key not in seen:
            seen.add(key)
            projected.append(skill.strip())
    story.append(Paragraph(_esc(", ".join(projected[:28])), styles["body"]))

    if candidate.projects:
        _section(story, "Foundation to build on")
        for item in candidate.projects[:2]:
            story.append(Paragraph(_esc(item.name or "Project"), styles["role"]))
            if item.description:
                story.append(Paragraph(_esc(item.description), styles["body"]))
            story.append(Spacer(1, 3))

    story.append(
        Paragraph(
            "Prepared by RecruiMate as a personal work plan. Recruiters should receive the "
            "as-is résumé; this document is for you.",
            styles["note"],
        )
    )

    doc.build(story)
    return buf.getvalue()


def tailored_pdfs(candidate, job: dict, posting_raw_text: str) -> dict[str, bytes]:
    """Compute the tailor payload once and render both PDF variants."""
    job_profile = job  # expects a JobProfile instance
    tailor = tailor_for_job(candidate, job_profile, posting_raw_text)
    return {
        "asis": build_asis_resume(candidate, tailor, {
            "id": getattr(job_profile, "id", ""),
            "title": getattr(job_profile, "job_title", ""),
            "company": getattr(job_profile, "company", ""),
        }),
        "dream": build_dream_resume(candidate, tailor, {
            "id": getattr(job_profile, "id", ""),
            "title": getattr(job_profile, "job_title", ""),
            "company": getattr(job_profile, "company", ""),
        }),
    }
