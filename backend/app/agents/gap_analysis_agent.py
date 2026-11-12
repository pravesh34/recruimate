"""Agent 4 — Gap Analysis."""
from __future__ import annotations

from ..schemas import CompatibilityReport, GapAnalysisReport
from ..services.roadmap_service import generate_roadmap


class GapAnalysisAgent:
    name = "gap_analysis_agent"
    label = "Skill Gap Analysis"

    def analyze(self, compatibility: CompatibilityReport, limit: int = 8) -> GapAnalysisReport:
        return generate_roadmap(compatibility, limit=limit)
