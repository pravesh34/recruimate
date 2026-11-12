"""LangGraph nodes. Each node is a thin adapter around an agent."""
from __future__ import annotations

import time
from typing import Any

from ..agents.compatibility_agent import CompatibilityAgent
from ..agents.gap_analysis_agent import GapAnalysisAgent
from ..agents.interview_agent import InterviewAgent
from ..agents.job_agent import JobAgent
from ..agents.resume_agent import ResumeAgent
from .state import WorkflowState


def _event(agent: str, status: str, provider: str = "", detail: str = "", ms: float = 0.0) -> dict:
    return {
        "agent": agent,
        "status": status,
        "provider": provider,
        "detail": detail,
        "duration_ms": round(ms, 1),
    }


def build_nodes(
    resume_agent: ResumeAgent,
    job_agent: JobAgent,
    compatibility_agent: CompatibilityAgent,
    gap_agent: GapAnalysisAgent,
    interview_agent: InterviewAgent,
) -> dict[str, Any]:
    async def resume_node(state: WorkflowState) -> dict[str, Any]:
        start = time.perf_counter()
        candidate, provider, error = await resume_agent.analyze_text(state.get("resume_text", ""))
        ms = (time.perf_counter() - start) * 1000
        out: dict[str, Any] = {
            "candidate": candidate,
            "providers": {**state.get("providers", {}), "resume_agent": provider},
            "activity": [_event("resume_agent", "completed", provider, f"{len(candidate.skills)} skills", ms)],
            "errors": [f"resume_agent: {error}"] if error else [],
        }
        return out

    async def job_node(state: WorkflowState) -> dict[str, Any]:
        start = time.perf_counter()
        job, provider, error = await job_agent.analyze(state.get("job_text", ""))
        ms = (time.perf_counter() - start) * 1000
        return {
            "job": job,
            "providers": {**state.get("providers", {}), "job_agent": provider},
            "activity": [
                _event("job_agent", "completed", provider, f"{len(job.required_skills)} required skills", ms)
            ],
            "errors": [f"job_agent: {error}"] if error else [],
        }

    async def compatibility_node(state: WorkflowState) -> dict[str, Any]:
        start = time.perf_counter()
        candidate = state["candidate"]
        job = state["job"]
        report = compatibility_agent.analyze(candidate, job, state.get("resume_text", ""))
        ms = (time.perf_counter() - start) * 1000
        return {
            "compatibility": report,
            "providers": {**state.get("providers", {}), "compatibility_agent": "deterministic"},
            "activity": [
                _event("compatibility_agent", "completed", "deterministic", f"{report.overall_score}/100", ms)
            ],
        }

    async def gap_node(state: WorkflowState) -> dict[str, Any]:
        start = time.perf_counter()
        gaps = gap_agent.analyze(state["compatibility"])
        ms = (time.perf_counter() - start) * 1000
        return {
            "gaps": gaps,
            "providers": {**state.get("providers", {}), "gap_analysis_agent": "deterministic"},
            "activity": [
                _event(
                    "gap_analysis_agent", "completed", "deterministic",
                    f"{len(gaps.priority_skills)} priorities", ms,
                )
            ],
        }

    async def interview_node(state: WorkflowState) -> dict[str, Any]:
        start = time.perf_counter()
        bank, provider, error = await interview_agent.build_question_bank(
            state.get("candidate"), state["job"], state.get("compatibility")
        )
        ms = (time.perf_counter() - start) * 1000
        return {
            "questions": bank,
            "providers": {**state.get("providers", {}), "interview_agent": provider},
            "activity": [
                _event("interview_agent", "completed", provider, f"{len(bank.questions)} questions", ms)
            ],
            "errors": [f"interview_agent: {error}"] if error else [],
        }

    async def report_node(state: WorkflowState) -> dict[str, Any]:
        report = {
            "overall_score": state["compatibility"].overall_score,
            "verdict": state["compatibility"].verdict,
            "priority_skills": state["gaps"].priority_skills,
            "question_count": len(state["questions"].questions),
            "estimated_hours": state["gaps"].total_estimated_hours,
            "providers": state.get("providers", {}),
            "errors": state.get("errors", []),
        }
        return {
            "final_report": report,
            "activity": [_event("supervisor", "completed", "", "analysis persisted")],
        }

    return {
        "resume": resume_node,
        "job": job_node,
        "compatibility": compatibility_node,
        "gaps": gap_node,
        "interview": interview_node,
        "report": report_node,
    }
