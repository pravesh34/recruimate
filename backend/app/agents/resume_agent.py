"""Agent 1 — Resume Intelligence."""
from __future__ import annotations

from ..prompts import RESUME_SYSTEM, RESUME_USER
from ..schemas import CandidateProfile
from ..services.resume_parser import clean_text, extract_text, heuristic_resume_profile
from ..services.skills import canonicalize_skill
from .base import BaseAgent


class ResumeAgent(BaseAgent):
    name = "resume_agent"
    label = "Resume Intelligence"

    async def from_file(self, filename: str, data: bytes) -> tuple[CandidateProfile, str, str]:
        text = extract_text(filename, data)
        return await self.analyze_text(text)

    async def analyze_text(self, text: str) -> tuple[CandidateProfile, str, str]:
        text = clean_text(text)
        baseline = heuristic_resume_profile(text)
        llm_profile, provider, error = await self._generate(
            RESUME_USER.format(resume_text=text[:14000]),
            CandidateProfile,
            system=RESUME_SYSTEM,
            temperature=0.1,
            max_tokens=2600,
        )
        if llm_profile is None:
            return baseline, provider, error
        return self._merge(baseline, llm_profile), provider, error

    def _merge(self, base: CandidateProfile, llm: CandidateProfile) -> CandidateProfile:
        def pick(a, b):
            return b if (b not in (None, "", [], {}) and b != 0) else a

        skills = self._union(
            [canonicalize_skill(s) or s for s in llm.skills],
            base.skills,
        )
        soft = self._union(llm.soft_skills, base.soft_skills)
        return CandidateProfile(
            name=pick(base.name, llm.name),
            headline=pick(base.headline, llm.headline),
            email=pick(base.email, llm.email),
            phone=pick(base.phone, llm.phone),
            location=pick(base.location, llm.location),
            summary=pick(base.summary, llm.summary),
            skills=skills,
            soft_skills=soft,
            education=llm.education or base.education,
            experience=llm.experience or base.experience,
            projects=llm.projects or base.projects,
            certifications=self._union(llm.certifications, base.certifications),
            achievements=self._union(llm.achievements, base.achievements),
            resume_strengths=self._union(llm.resume_strengths, base.resume_strengths)[:8],
            resume_weaknesses=self._union(llm.resume_weaknesses, base.resume_weaknesses)[:8],
            improvement_suggestions=self._union(
                llm.improvement_suggestions, base.improvement_suggestions
            )[:8],
            unknown_fields=self._union(llm.unknown_fields, base.unknown_fields),
            years_experience=max(base.years_experience, llm.years_experience),
        )
