"""Agent 2 — Job Intelligence."""
from __future__ import annotations

from ..prompts import JOB_SYSTEM, JOB_USER
from ..schemas import JobProfile
from ..services.job_parser import heuristic_job_profile
from ..services.skills import canonicalize_skill
from .base import BaseAgent


class JobAgent(BaseAgent):
    name = "job_agent"
    label = "Job Intelligence"

    async def analyze(self, text: str) -> tuple[JobProfile, str, str]:
        text = (text or "").strip()
        baseline = heuristic_job_profile(text)
        if len(text) < 20:
            return baseline, "heuristic", "Job description is too short for reliable extraction."
        llm_profile, provider, error = await self._generate(
            JOB_USER.format(job_text=text[:14000]),
            JobProfile,
            system=JOB_SYSTEM,
            temperature=0.1,
            max_tokens=2000,
        )
        if llm_profile is None:
            return baseline, provider, error
        return self._merge(baseline, llm_profile), provider, error

    def _merge(self, base: JobProfile, llm: JobProfile) -> JobProfile:
        llm_required = [canonicalize_skill(s) or s for s in llm.required_skills]
        llm_preferred = [
            canonicalize_skill(s) or s for s in llm.preferred_skills
            if (canonicalize_skill(s) or s) not in llm_required
        ]
        required = self._union(llm_required, base.required_skills)
        preferred = [
            s for s in self._union(llm_preferred, base.preferred_skills) if s not in required
        ]
        return JobProfile(
            job_title=llm.job_title or base.job_title,
            company=llm.company or base.company,
            location=llm.location or base.location,
            employment_type=llm.employment_type or base.employment_type,
            role_category=llm.role_category if llm.role_category != "general" else base.role_category,
            required_skills=required,
            preferred_skills=preferred,
            experience_requirements=self._union(llm.experience_requirements, base.experience_requirements),
            education_requirements=self._union(llm.education_requirements, base.education_requirements),
            responsibilities=self._union(llm.responsibilities, base.responsibilities)[:12],
            behavioural_expectations=self._union(
                llm.behavioural_expectations, base.behavioural_expectations
            )[:8],
            certifications=self._union(llm.certifications, base.certifications),
            min_years_experience=max(base.min_years_experience, llm.min_years_experience),
        )
