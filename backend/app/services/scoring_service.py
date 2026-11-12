"""Deterministic, explainable compatibility scoring.

The LLM never invents the percentages: technical coverage, experience, projects,
education and certifications are computed here, then optionally narrated by an
agent (the numbers stay untouched).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..schemas import (
    CandidateProfile,
    CategoryScore,
    CompatibilityReport,
    JobProfile,
    SkillMatch,
)
from .embedding_service import EmbeddingService, get_embedding_service
from .skills import SKILL_CATEGORIES, SOFT_SKILLS

WEIGHTS = {
    "Technical skills": 0.40,
    "Relevant experience": 0.25,
    "Projects": 0.20,
    "Education": 0.10,
    "Certifications": 0.05,
}

DEGREE_LEVELS = {
    "phd": 4, "doctor": 4,
    "master": 3, "mba": 3, "m.tech": 3, "m.sc": 3, "m.e": 3, "msc": 3,
    "bachelor": 2, "b.tech": 2, "b.sc": 2, "b.e": 2, "bsc": 2, "btech": 2,
    "diploma": 1, "associate": 1,
}


def _calibrate(similarity: float) -> float:
    """Map short-text cosine similarity onto a usable 0..1 relevance band."""
    return max(0.0, min(1.0, (similarity - 0.05) / 0.55))


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _degree_level(text: str) -> int:
    lower = text.lower()
    level = 0
    for key, value in DEGREE_LEVELS.items():
        if key in lower:
            level = max(level, value)
    return level


def _sentence_evidence(resume_text: str, skill: str) -> str:
    if not resume_text:
        return ""
    sentences = re.split(r"(?<=[.!?;])\s+|\n+", resume_text)
    for sentence in sentences:
        if skill.lower() in sentence.lower():
            cleaned = re.sub(r"\s+", " ", sentence).strip(" -•|")
            if 8 <= len(cleaned) <= 260:
                return cleaned
    return ""


@dataclass
class _Match:
    job_skill: str
    candidate_skill: str
    similarity: float
    status: str


class ScoringService:
    def __init__(self, embeddings: EmbeddingService | None = None):
        self.embeddings = embeddings or get_embedding_service()

    def _best_match(self, skill: str, candidate_skills: list[str]) -> _Match:
        best = _Match(skill, "", 0.0, "missing")
        for candidate in candidate_skills:
            if skill.lower() == candidate.lower():
                return _Match(skill, candidate, 1.0, "matched")
            if skill.lower() in candidate.lower() or candidate.lower() in skill.lower():
                return _Match(skill, candidate, 0.85, "matched")
        if candidate_skills:
            sims = self.embeddings.similarities(skill, candidate_skills)
            idx = int(max(range(len(sims)), key=lambda i: sims[i]))
            sim = sims[idx]
            if sim >= 0.78:
                return _Match(skill, candidate_skills[idx], sim, "matched")
            if sim >= 0.58:
                return _Match(skill, candidate_skills[idx], sim, "partial")
            best.similarity = sim
        return best

    # ------------------------------------------------------------------ main
    def score(
        self,
        candidate: CandidateProfile,
        job: JobProfile,
        resume_text: str = "",
        *,
        method_note: str = "",
    ) -> CompatibilityReport:
        required = [s for s in job.required_skills if s not in SOFT_SKILLS]
        preferred = [s for s in job.preferred_skills if s not in SOFT_SKILLS and s not in required]
        candidate_skills = list(dict.fromkeys(candidate.skills))
        all_job_skills = list(dict.fromkeys(required + preferred))

        matches: list[_Match] = []
        for skill in all_job_skills:
            matches.append(self._best_match(skill, candidate_skills))

        def coverage(skills: list[str]) -> tuple[float, list[_Match]]:
            relevant = [m for m in matches if m.job_skill in skills]
            if not relevant:
                return 0.0, []
            total = sum(1.0 if m.status == "matched" else 0.5 if m.status == "partial" else 0.0 for m in relevant)
            return total / len(relevant), relevant

        required_cov, required_matches = coverage(required)
        preferred_cov, preferred_matches = coverage(preferred)
        if required and preferred:
            technical = (required_cov * 0.75 + preferred_cov * 0.25) * 100
        elif required:
            technical = required_cov * 100
        elif preferred:
            technical = preferred_cov * 100
        else:
            technical = 55.0
        technical = max(0.0, min(100.0, technical))

        # ---------------------------------------------------------- experience
        min_years = float(job.min_years_experience or 0)
        cand_years = float(candidate.years_experience or 0)
        exp_text = " ".join(
            f"{e.title} {e.company} {e.description} {' '.join(e.highlights)}" for e in candidate.experience
        )
        job_text = " ".join(
            [job.job_title, " ".join(job.required_skills), " ".join(job.responsibilities)]
        )
        relevance = 0.0
        if exp_text.strip():
            relevance = _calibrate(self.embeddings.similarity(exp_text[:4000], job_text[:4000]))
        if min_years > 0:
            year_score = min(1.0, cand_years / min_years) if cand_years else 0.0
            experience = year_score * 70 + relevance * 30
            exp_explanation = (
                f"{cand_years:g} years detected against a {min_years:g}-year requirement; "
                f"experience relevance {relevance * 100:.0f}%."
            )
        else:
            base = 78.0 if cand_years > 0 else 48.0
            experience = base * 0.55 + relevance * 100 * 0.45
            exp_explanation = (
                "No explicit year requirement; scored on evidence of relevant experience."
                if cand_years
                else "No year requirement, but no work experience was detected."
            )
        experience = max(0.0, min(100.0, experience))

        # -------------------------------------------------------------- projects
        project_text = " ".join(
            f"{p.name} {p.description} {' '.join(p.technologies)}" for p in candidate.projects
        )
        project_skills = list(
            dict.fromkeys([s for p in candidate.projects for s in p.technologies])
        )
        proj_matches = [self._best_match(s, project_skills) for s in all_job_skills] if project_skills else []
        proj_cov = (
            sum(1.0 if m.status == "matched" else 0.5 if m.status == "partial" else 0.0 for m in proj_matches)
            / len(all_job_skills)
            if all_job_skills and project_skills
            else 0.0
        )
        proj_relevance = (
            _calibrate(self.embeddings.similarity(project_text[:4000], job_text[:4000]))
            if project_text.strip()
            else 0.0
        )
        if candidate.projects:
            projects = proj_cov * 60 + proj_relevance * 30 + min(len(candidate.projects), 3) * (10 / 3)
            proj_explanation = (
                f"{len(candidate.projects)} project(s); {proj_cov * 100:.0f}% of job skills appear in project evidence."
            )
        else:
            projects = 12.0
            proj_explanation = "No projects found; this is weighted heavily for early-career roles."
        projects = max(0.0, min(100.0, projects))

        # ------------------------------------------------------------- education
        cand_degree_text = " ".join(
            f"{e.degree} {e.field} {e.institution} {e.details}" for e in candidate.education
        )
        edu_level = _degree_level(cand_degree_text)
        edu_requirements = " ".join(job.education_requirements)
        if not candidate.education:
            education = 20.0
            edu_explanation = "No education section detected."
        elif not edu_requirements.strip():
            education = 82.0
            edu_explanation = "No specific education requirement in the posting; a degree is listed."
        else:
            required_level = _degree_level(edu_requirements)
            if required_level and edu_level:
                level_ratio = min(1.0, edu_level / required_level)
                education = 55 + level_ratio * 30
            elif required_level:
                education = 40.0
            else:
                education = 65.0
            field_rel = _calibrate(self.embeddings.similarity(cand_degree_text, edu_requirements))
            education += field_rel * 15
            edu_explanation = (
                f"Degree level {edu_level or 'unknown'} against requirement; field relevance {field_rel * 100:.0f}%."
            )
        education = max(0.0, min(100.0, education))

        # -------------------------------------------------------- certifications
        cand_certs = [c.lower() for c in candidate.certifications]
        if job.certifications:
            wanted = [re.sub(r"[^a-z0-9 ]", "", c.lower()) for c in job.certifications]
            hits = 0
            for want in wanted:
                keywords = [w for w in want.split() if len(w) > 3]
                if keywords and any(all(k in cert for k in keywords[:3]) for cert in cand_certs):
                    hits += 1
            certs = (hits / max(1, len(wanted))) * 100
            cert_explanation = f"{hits}/{len(wanted)} requested certification area(s) evidenced."
        else:
            certs = 72.0 if candidate.certifications else 55.0
            cert_explanation = (
                "No certification requirement; candidate lists certifications."
                if candidate.certifications
                else "No certification requirement and none listed (neutral)."
            )
        certs = max(0.0, min(100.0, certs))

        categories = [
            CategoryScore(
                name="Technical skills", score=round(technical, 1), weight=WEIGHTS["Technical skills"],
                weighted=round(technical * WEIGHTS["Technical skills"], 2),
                explanation=(
                    f"Required-skill coverage {required_cov * 100:.0f}% and preferred-skill coverage "
                    f"{preferred_cov * 100:.0f}% across {len(all_job_skills)} skills."
                ),
            ),
            CategoryScore(
                name="Relevant experience", score=round(experience, 1), weight=WEIGHTS["Relevant experience"],
                weighted=round(experience * WEIGHTS["Relevant experience"], 2), explanation=exp_explanation,
            ),
            CategoryScore(
                name="Projects", score=round(projects, 1), weight=WEIGHTS["Projects"],
                weighted=round(projects * WEIGHTS["Projects"], 2), explanation=proj_explanation,
            ),
            CategoryScore(
                name="Education", score=round(education, 1), weight=WEIGHTS["Education"],
                weighted=round(education * WEIGHTS["Education"], 2), explanation=edu_explanation,
            ),
            CategoryScore(
                name="Certifications", score=round(certs, 1), weight=WEIGHTS["Certifications"],
                weighted=round(certs * WEIGHTS["Certifications"], 2), explanation=cert_explanation,
            ),
        ]
        overall = round(sum(c.weighted for c in categories), 1)
        verdict = self.verdict(overall)

        matched, partial, missing = [], [], []
        for m in matches:
            ev = _sentence_evidence(resume_text, m.candidate_skill or m.job_skill)
            item = SkillMatch(
                skill=m.job_skill,
                matched_with=m.candidate_skill if m.status != "missing" else "",
                similarity=round(m.similarity, 2),
                status=m.status,  # type: ignore[arg-type]
                evidence=ev or ("Listed in the skills section." if m.status == "matched" else ""),
            )
            {"matched": matched, "partial": partial, "missing": missing}[m.status].append(item)

        evidence = [
            f"Technical: {c.explanation}" for c in categories[:1]
        ]
        for item in matched[:6]:
            if item.evidence:
                evidence.append(f"{item.skill}: {item.evidence}")
        evidence.append(f"Experience: {exp_explanation}")
        evidence.append(f"Projects: {proj_explanation}")

        strengths: list[str] = []
        if matched:
            strengths.append("Matches required skills: " + ", ".join(i.skill for i in matched[:6]) + ".")
        if cand_years:
            strengths.append(f"Brings {cand_years:g} year(s) of experience evidence.")
        if candidate.projects:
            strengths.append(f"Has {len(candidate.projects)} project(s) that can be discussed in interviews.")
        if not strengths:
            strengths.append("Some transferable skills were detected; focus on evidence and projects.")

        concerns: list[str] = []
        if missing:
            concerns.append("Missing or unproven skills: " + ", ".join(i.skill for i in missing[:6]) + ".")
        if partial:
            concerns.append("Partially matched skills need stronger evidence: " + ", ".join(i.skill for i in partial[:4]) + ".")
        if min_years and cand_years < min_years:
            concerns.append(f"Posting asks for {min_years:g}+ years; resume shows {cand_years:g}.")
        if not candidate.projects:
            concerns.append("No projects were detected, reducing proof of practical ability.")
        if not candidate.experience:
            concerns.append("No work experience was detected.")
        if not concerns:
            concerns.append("No major gaps detected; keep evidence specific and quantified.")

        explanation = (
            f"{verdict} for {job.job_title or 'this role'}. The overall score is a weighted, deterministic "
            f"combination of skills (40%), experience (25%), projects (20%), education (10%) and "
            f"certifications (5%). {len(matched)} required/preferred skills matched, {len(partial)} partial "
            f"and {len(missing)} missing. Scores explain evidence in your resume only; they are not a hiring decision."
        )
        if method_note:
            explanation += f" {method_note}"

        return CompatibilityReport(
            overall_score=overall,
            verdict=verdict,
            category_scores=categories,
            matched_skills=matched,
            partially_matched_skills=partial,
            missing_skills=missing,
            evidence=evidence,
            explanation=explanation,
            strengths=strengths,
            concerns=concerns,
            method="deterministic weights + embedding similarity",
        )

    @staticmethod
    def verdict(score: float) -> str:
        if score >= 80:
            return "Strong match"
        if score >= 65:
            return "Good match"
        if score >= 50:
            return "Moderate match"
        if score >= 35:
            return "Stretch match"
        return "Low match"


def top_gaps(report: CompatibilityReport, limit: int = 6) -> list[str]:
    priority = [m.skill for m in report.missing_skills] + [m.skill for m in report.partially_matched_skills]
    return priority[:limit]


def category_context(report: CompatibilityReport) -> str:
    return "; ".join(f"{c.name} {c.score:.0f}/100" for c in report.category_scores)


__all__ = ["ScoringService", "top_gaps", "category_context", "WEIGHTS", "SKILL_CATEGORIES"]
