"""Agent 3 — Compatibility.

Deliberately LLM-free: scores are computed with deterministic weights and
embedding similarity so percentages can always be explained and reproduced.
"""
from __future__ import annotations

from ..schemas import CandidateProfile, CompatibilityReport, JobProfile
from ..services.scoring_service import ScoringService


class CompatibilityAgent:
    name = "compatibility_agent"
    label = "Compatibility"

    def __init__(self, scoring: ScoringService | None = None):
        self.scoring = scoring or ScoringService()

    def analyze(
        self,
        candidate: CandidateProfile,
        job: JobProfile,
        resume_text: str = "",
        *,
        method_note: str = "",
    ) -> CompatibilityReport:
        return self.scoring.score(candidate, job, resume_text, method_note=method_note)
