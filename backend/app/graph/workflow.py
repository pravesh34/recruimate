"""Supervisor workflow.

Uses LangGraph when available (resume + job in parallel, then compatibility,
gap analysis, interview preparation and a final report). If LangGraph is not
installed, the same DAG runs through an async fallback orchestrator, so the
product never depends on an optional import success.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from ..agents.compatibility_agent import CompatibilityAgent
from ..agents.gap_analysis_agent import GapAnalysisAgent
from ..agents.interview_agent import InterviewAgent
from ..agents.job_agent import JobAgent
from ..agents.resume_agent import ResumeAgent
from ..gateway import GatewayManager
from .nodes import build_nodes
from .state import DEFAULT_STATE, WorkflowState

logger = logging.getLogger("recruimate.workflow")


class SupervisorAgent:
    """Coordinates the five specialist agents through a single typed workflow."""

    name = "supervisor"

    def __init__(self, gateway: GatewayManager):
        self.gateway = gateway
        self.resume_agent = ResumeAgent(gateway)
        self.job_agent = JobAgent(gateway)
        self.compatibility_agent = CompatibilityAgent()
        self.gap_agent = GapAnalysisAgent()
        self.interview_agent = InterviewAgent(gateway)
        self.nodes = build_nodes(
            self.resume_agent,
            self.job_agent,
            self.compatibility_agent,
            self.gap_agent,
            self.interview_agent,
        )
        self.graph, self.engine = self._build_graph()

    def _build_graph(self):
        try:
            from langgraph.graph import END, START, StateGraph
        except Exception:
            return None, "async-fallback"
        try:
            graph = StateGraph(WorkflowState)
            for name, fn in self.nodes.items():
                graph.add_node(name, fn)
            graph.add_edge(START, "resume")
            graph.add_edge(START, "job")
            graph.add_edge(["resume", "job"], "compatibility")
            graph.add_edge("compatibility", "gaps")
            graph.add_edge("gaps", "interview")
            graph.add_edge("interview", "report")
            graph.add_edge("report", END)
            return graph.compile(), "langgraph"
        except Exception as exc:  # pragma: no cover - depends on optional package
            logger.warning("LangGraph unavailable, using async orchestrator: %s", exc)
            return None, "async-fallback"

    async def run(self, resume_text: str, job_text: str) -> WorkflowState:
        state: WorkflowState = {
            **DEFAULT_STATE,
            "resume_text": resume_text,
            "job_text": job_text,
            "providers": {},
            "errors": [],
            "activity": [],
        }
        if self.graph is not None:
            result = await self.graph.ainvoke(state)
            # LangGraph may deep-copy reducers; ensure required keys exist.
            for key, value in DEFAULT_STATE.items():
                result.setdefault(key, value)
            return result  # type: ignore[return-value]

        # ------------------------------------------------- async fallback DAG
        resume_task = asyncio.create_task(self.nodes["resume"](state))
        job_task = asyncio.create_task(self.nodes["job"](state))
        resume_out, job_out = await asyncio.gather(resume_task, job_task, return_exceptions=True)

        def merge(out: Any) -> dict:
            if isinstance(out, BaseException):
                return {"errors": [f"workflow: {out}"]}
            return out

        state = _apply(state, merge(resume_out))
        state = _apply(state, merge(job_out))
        if not state.get("candidate") or not state.get("job"):
            state["errors"].append("workflow: missing candidate or job profile")
            return state
        for node in ("compatibility", "gaps", "interview", "report"):
            out = await self.nodes[node](state)
            state = _apply(state, out)
        return state


def _apply(state: WorkflowState, update: dict[str, Any]) -> WorkflowState:
    new_state = dict(state)
    for key, value in update.items():
        if key == "activity":
            new_state["activity"] = list(state.get("activity", [])) + list(value or [])
        elif key == "errors":
            new_state["errors"] = list(state.get("errors", [])) + list(value or [])
        elif key == "providers":
            new_state["providers"] = {**state.get("providers", {}), **(value or {})}
        else:
            new_state[key] = value
    return new_state  # type: ignore[return-value]
