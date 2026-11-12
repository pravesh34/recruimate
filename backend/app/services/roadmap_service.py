"""Personalised learning roadmap generation (deterministic, no fabricated links)."""
from __future__ import annotations

from ..schemas import (
    CategoryScore,
    CompatibilityReport,
    GapAnalysisReport,
    RoadmapStep,
)
from .skills import skill_template


def generate_roadmap(report: CompatibilityReport, limit: int = 8) -> GapAnalysisReport:
    missing = list(report.missing_skills)
    partial = list(report.partially_matched_skills)

    ordered: list[tuple[str, str, float]] = []
    for item in missing:
        ordered.append((item.skill, "high", item.similarity))
    for item in partial:
        ordered.append((item.skill, "medium", item.similarity))
    ordered = ordered[:limit]

    steps: list[RoadmapStep] = []
    total_hours = 0.0
    for index, (skill, priority, similarity) in enumerate(ordered, start=1):
        template = skill_template(skill)
        hours = template.base_hours * (1.25 if priority == "high" else 1.0)
        if similarity > 0.5:
            hours *= 0.65  # partial overlap means less ground to cover
        hours = round(max(2.0, hours), 1)
        total_hours += hours
        steps.append(
            RoadmapStep(
                order=index,
                skill=skill,
                title=f"Strengthen {skill}",
                description=(
                    f"Close the {priority}-priority gap in {skill}. Build one small artefact and be able "
                    "to explain the trade-offs out loud."
                ),
                study_topics=template.topics[:5],
                practice_project=template.project,
                estimated_hours=hours,
                priority=priority,  # type: ignore[arg-type]
                resources=[],
            )
        )

    project_ideas = [
        step.practice_project for step in steps[:4] if step.practice_project
    ]
    # One integrating project that combines the top gaps.
    if steps:
        top = [s.skill for s in steps[:3]]
        project_ideas.append(
            f"Capstone: build a small end-to-end application that uses {', '.join(top)}. "
            "Document the problem, architecture, trade-offs and measured result."
        )

    study_topics: list[str] = []
    for step in steps:
        study_topics.extend(step.study_topics[:2])
    study_topics = list(dict.fromkeys(study_topics))[:16]

    priority_skills = [s.skill for s in steps]
    overall = report.overall_score
    if not steps:
        summary = (
            f"No major skill gaps were found for this role (compatibility {overall:.0f}/100). "
            "Shift preparation to depth: rehearse project stories, system design and behavioural answers."
        )
    else:
        summary = (
            f"Compatibility is {overall:.0f}/100 ({report.verdict}). The highest-leverage gaps are "
            f"{', '.join(priority_skills[:4])}. The roadmap below is ordered by job importance and "
            f"requires about {total_hours:.0f} hours of focused work."
        )

    plan = _preparation_plan(priority_skills, total_hours, bool(steps))
    return GapAnalysisReport(
        summary=summary,
        priority_skills=priority_skills,
        learning_roadmap=steps,
        recommended_projects=project_ideas,
        study_topics=study_topics,
        preparation_plan=plan,
        total_estimated_hours=round(total_hours, 1),
    )


def _preparation_plan(priority: list[str], total_hours: float, has_gaps: bool) -> list[str]:
    if not has_gaps:
        return [
            "Re-read the job description and write a one-page evidence sheet mapping each requirement to proof.",
            "Rehearse two project stories with the STAR structure (situation, task, action, result).",
            "Complete two mock interviews and review the weakest evaluation dimension after each.",
            "Prepare three questions about the team, product and engineering process.",
        ]
    first = priority[0] if priority else "the top gap"
    second = priority[1] if len(priority) > 1 else "the next gap"
    weekly = max(4, round(total_hours / 4))
    return [
        f"Week 1 — Fundamentals: complete the '{first}' topics and ship the small practice exercise ({weekly}h target).",
        f"Week 2 — Applied depth: complete '{second}' and start the integrating capstone project.",
        "Week 3 — Evidence: finish the capstone, quantify the result, and rewrite one resume bullet for each new skill.",
        "Week 4 — Interview loop: generate a question bank, run two mock interviews, and drill the weakest dimension.",
        "Daily habit: 45–60 minutes of deliberate practice plus 10 minutes of spoken explanation without notes.",
    ]


def readiness_from_scores(category_scores: list[CategoryScore]) -> str:
    if not category_scores:
        return "unknown"
    score = sum(c.score * c.weight for c in category_scores)
    return "interview-ready" if score >= 75 else "nearly ready" if score >= 55 else "needs preparation"
