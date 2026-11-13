"""Deterministic resume tailoring for one target job.

Reorders the candidate's *real* bullets so the ones that evidence the job's
required skills come first, tags each bullet with the skills it proves, and
drafts a cover letter from actual profile evidence. No experience is invented;
the plan-of-approach note references the candidate's own gap list.
"""
from __future__ import annotations

import re


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.;])\s+", (text or "").strip())
    return [p.strip() for p in parts if len(p.strip()) >= 25]


def _collect_bullets(candidate) -> list[dict]:
    bullets: list[dict] = []
    for exp in candidate.experience or []:
        context = " at ".join(part for part in (exp.title, exp.company) if part) or "Experience"
        for highlight in exp.highlights or []:
            bullets.append({"text": highlight, "context": context})
        for sentence in _split_sentences(exp.description):
            bullets.append({"text": sentence, "context": context})
    for project in candidate.projects or []:
        context = f"Project: {project.name}" if project.name else "Project"
        for sentence in _split_sentences(project.description):
            bullets.append({"text": sentence, "context": context, "tech": project.technologies or []})
        if not project.description and project.technologies:
            bullets.append(
                {
                    "text": f"Built {project.name} using {', '.join(project.technologies[:4])}.",
                    "context": context,
                    "tech": project.technologies or [],
                }
            )
    for achievement in candidate.achievements or []:
        bullets.append({"text": achievement, "context": "Achievement"})
    return bullets


def _bullet_match(text_lower: str, required: list[str]) -> list[str]:
    hits = []
    for skill in required:
        s = skill.lower().strip()
        if s and s in text_lower:
            hits.append(skill)
    return hits


def tailor_for_job(candidate, job_profile, posting_raw_text: str) -> dict:
    required = [s for s in (job_profile.required_skills or []) if s]
    posting_words = set(
        re.findall(r"[a-z][a-z+#.\-]{2,}", (posting_raw_text or "").lower())
    )

    scored: list[dict] = []
    for bullet in _collect_bullets(candidate):
        tech = " ".join(bullet.get("tech", [])).lower()
        text_lower = (bullet["text"] + " " + tech).lower()
        matched = _bullet_match(text_lower, required)
        keyword_overlap = len(posting_words & set(re.findall(r"[a-z][a-z+#.\-]{2,}", text_lower)))
        scored.append(
            {
                **bullet,
                "matched": matched,
                "relevance": len(matched) * 3 + min(keyword_overlap, 6) * 0.5,
            }
        )

    scored.sort(key=lambda b: -b["relevance"])
    strong = [b for b in scored if b["matched"]]
    filler = [b for b in scored if not b["matched"]]
    chosen = (strong + filler)[:8]

    bullets_out = [
        {
            "text": b["text"].rstrip(".") + ("." if not b["text"].rstrip().endswith((".", "!", "?")) else ""),
            "context": b["context"],
            "matched_skills": b["matched"][:4],
        }
        for b in chosen
    ]

    candidate_skills = {s.lower() for s in (candidate.skills or [])}
    matched_required = [s for s in required if s.lower() in candidate_skills]
    missing_required = [s for s in required if s.lower() not in candidate_skills][:6]

    cover_letter = _cover_letter(candidate, job_profile, matched_required, missing_required, bullets_out[:3])

    return {
        "bullets": bullets_out,
        "summary": {
            "matched_skills": matched_required,
            "missing_skills": missing_required,
            "years_experience": candidate.years_experience,
            "bullet_pool": len(scored),
        },
        "cover_letter": cover_letter,
    }


def _cover_letter(candidate, job_profile, matched: list[str], missing: list[str], bullets: list[dict]) -> str:
    company = job_profile.company or "your team"
    title = job_profile.job_title or "the role"
    name = candidate.name or "Candidate"
    years = candidate.years_experience
    headline = (candidate.headline or candidate.summary or "").strip().splitlines()[0][:160] if (
        candidate.headline or candidate.summary
    ) else ""
    location = candidate.location or ""

    lines: list[str] = []
    lines.append(f"Dear {company} Hiring Team,")
    lines.append("")
    opener = f"I am applying for the {title} position at {company}."
    if years:
        opener += f" I bring {years:g} years of hands-on experience"
    elif headline:
        opener += f" I work as a {headline}"
    if headline and years:
        opener += f", working as a {headline}"
    opener += "."
    lines.append(opener)

    if matched:
        lines.append("")
        lines.append(
            "My background maps directly onto the core requirements: "
            + ", ".join(matched[:5])
            + "."
        )
    if bullets:
        lines.append("")
        lines.append("Representative work:")
        for b in bullets:
            lines.append(f"  • {b['text']} ({b['context']})")
    if missing:
        lines.append("")
        lines.append(
            "I also see the role values "
            + ", ".join(missing[:3])
            + ". My current development plan targets exactly these gaps with "
            "structured study topics and a practice project, so I can ramp on them quickly."
        )
    lines.append("")
    closing = "I would welcome the chance to walk through my fit in a conversation."
    if location:
        closing += f" I am based in {location}."
    lines.append(closing)
    lines.append("")
    lines.append("Best regards,")
    lines.append(name)
    return "\n".join(lines)


def tailor_markdown(tailor: dict, job_title: str, company: str) -> str:
    """Markdown export: tailored resume section + cover letter."""
    summary = tailor["summary"]
    lines = [
        f"# Tailored application — {job_title}",
        company,
        "",
        "## Resume bullets (reordered for this role)",
        "",
        f"Proven: {', '.join(summary['matched_skills']) or '—'}",
        "",
    ]
    for b in tailor["bullets"]:
        tag = f" `{'` `'.join(b['matched_skills'])}`" if b["matched_skills"] else ""
        lines.append(f"- **[{b['context']}]** {b['text']}{tag}")
    lines += ["", "## Cover letter", "", tailor["cover_letter"], ""]
    return "\n".join(lines)


def tailor_html(tailor: dict, job_title: str, company: str) -> str:
    """Print-friendly HTML (browser → Save as PDF on Android)."""
    summary = tailor["summary"]
    bullets = "".join(
        f"<li><span class=\"ctx\">{b['context']}</span> {b['text']}"
        + (
            "".join(f"<em>{s}</em>" for s in b["matched_skills"])
            if b["matched_skills"]
            else ""
        )
        + "</li>"
        for b in tailor["bullets"]
    )
    letter = tailor["cover_letter"].replace("\n", "<br/>")
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>Tailored application — {job_title}</title>
<style>
body{{font-family:Georgia,'Times New Roman',serif;max-width:760px;margin:24px auto;padding:0 18px;color:#1a2233;line-height:1.55}}
h1{{font-size:22px;margin-bottom:2px}} .sub{{color:#5a6478;margin-bottom:18px}}
h2{{font-size:16px;border-bottom:1px solid #dde;padding-bottom:4px;margin-top:26px}}
li{{margin:8px 0}} .ctx{{color:#5a6478;font-size:13px;display:block}}
em{{background:#eef2ff;border-radius:4px;padding:0 5px;margin-left:4px;font-style:normal;font-size:12px;color:#3346c2}}
.letter{{background:#fafbfe;border:1px solid #e4e8f2;border-radius:10px;padding:16px}}
@media print{{body{{margin:0}} .noprint{{display:none}}}}
</style></head><body>
<h1>Tailored application — {job_title}</h1>
<p class="sub">{company} · proven: {', '.join(summary['matched_skills']) or '—'}
· gaps: {', '.join(summary['missing_skills'][:4]) or '—'}</p>
<h2>Resume bullets (reordered for this role)</h2><ul>{bullets}</ul>
<h2>Cover letter</h2><div class="letter">{letter}</div>
<p class="noprint" style="color:#889">Tip: use your browser's Print → Save as PDF.</p>
</body></html>"""
