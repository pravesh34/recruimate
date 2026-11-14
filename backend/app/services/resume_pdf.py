"""Canonical PDF rendering for resumes.

Every upload is stored in its original form *and* rendered to a clean,
ATS-friendly PDF (single column, standard fonts, no images, no tables).
That PDF is what the app serves for "Open my resume" and what the tailoring
and export flows build on, so the candidate always has one canonical
document regardless of whether they uploaded PDF, DOCX, TXT or Markdown.

Rendering is intentionally deterministic and dependency-light: reportlab
only, no network, no external assets.
"""
from __future__ import annotations

import re
from io import BytesIO
from typing import Iterable

from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer

# Section headings we detect in plain resume text.
_SECTION_TITLES = {
    "summary",
    "profile",
    "professional summary",
    "objective",
    "skills",
    "technical skills",
    "core skills",
    "experience",
    "work experience",
    "professional experience",
    "employment",
    "projects",
    "personal projects",
    "education",
    "certifications",
    "certificates",
    "achievements",
    "awards",
    "languages",
    "interests",
    "hobbies",
    "activities",
    "publications",
    "references",
    "contact",
    "links",
}

_NAME_LINE = re.compile(r"^[A-Z][\w'.\- ]{2,60}$")
_BULLET = re.compile(r"^\s*[-•*▪◦–—]\s+(.*)$")
_CONTACT = re.compile(r"(@|https?://|linkedin\.com|github\.com|\+?\d[\d\s\-()]{6,})", re.I)


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    name_style = ParagraphStyle(
        "ResumeName",
        parent=base["Title"],
        fontName="Helvetica-Bold",
        fontSize=17,
        leading=20,
        alignment=TA_LEFT,
        spaceAfter=2,
        textColor="#111827",
    )
    contact_style = ParagraphStyle(
        "ResumeContact",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=13,
        textColor="#374151",
        spaceAfter=10,
    )
    section_style = ParagraphStyle(
        "ResumeSection",
        parent=base["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11.5,
        leading=14,
        spaceBefore=10,
        spaceAfter=4,
        textColor="#111827",
    )
    body_style = ParagraphStyle(
        "ResumeBody",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=13.5,
        spaceAfter=3,
        textColor="#1f2937",
    )
    return {
        "name": name_style,
        "contact": contact_style,
        "section": section_style,
        "body": body_style,
    }


def _escape(text: str) -> str:
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _split_sections(lines: Iterable[str]) -> tuple[list[str], list[tuple[str, list[str]]]]:
    """Split plain resume text into a header block and (section, lines) pairs."""
    header: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    current_title: str | None = None
    current_lines: list[str] = []

    for raw in lines:
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            if current_title is not None:
                current_lines.append("")
            continue
        lowered = stripped.lower().rstrip(":").strip()
        looks_like_section = (
            lowered in _SECTION_TITLES
            and len(stripped) <= 40
            and stripped == stripped.upper()
        ) or (lowered in _SECTION_TITLES and len(stripped) <= 40 and not stripped[0].islower())
        if looks_like_section:
            if current_title is not None:
                sections.append((current_title, current_lines))
            current_title = stripped.rstrip(":").strip()
            current_lines = []
            continue
        if current_title is None:
            header.append(stripped)
        else:
            current_lines.append(stripped)
    if current_title is not None:
        sections.append((current_title, current_lines))
    return header, sections


def render_resume_pdf(raw_text: str, title: str = "Resume") -> bytes:
    """Render resume text to a single-column PDF and return the bytes."""
    styles = _styles()
    text = (raw_text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    header, sections = _split_sections(lines)

    story = []
    name = header[0] if header and _NAME_LINE.match(header[0]) else ""
    if name:
        story.append(Paragraph(_escape(name), styles["name"]))
        contact_lines = header[1:4] if name else header[:3]
    else:
        contact_lines = header[:3]
    for line in contact_lines:
        if line:
            story.append(Paragraph(_escape(line), styles["contact"]))
    if name:
        story.append(Spacer(1, 2))

    for section_title, section_lines in sections:
        story.append(Paragraph(_escape(section_title.upper()), styles["section"]))
        bullets: list[str] = []
        paragraphs: list[str] = []

        def flush() -> None:
            if paragraphs:
                story.append(Paragraph(_escape(" ".join(paragraphs)), styles["body"]))
                paragraphs.clear()

        for line in section_lines:
            bullet = _BULLET.match(line)
            if bullet:
                flush()
                bullets.append(_escape(bullet.group(1).strip()))
            elif bullets:
                # continuation of the previous bullet
                bullets[-1] = f"{bullets[-1]} {_escape(line.strip())}"
            else:
                paragraphs.append(line.strip())
        flush()
        if bullets:
            story.append(
                ListFlowable(
                    [ListItem(Paragraph(item, styles["body"])) for item in bullets],
                    bulletType="bullet",
                    start="•",
                    leftIndent=12,
                    bulletFontSize=7,
                    spaceAfter=2,
                )
            )

    if not story:
        story.append(Paragraph(_escape("(No resume text available)"), styles["body"]))

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=title,
        author="RecruiMate",
    )
    doc.build(story)
    return buffer.getvalue()
