"""Typed shared state for the LangGraph supervisor."""
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from ..schemas import (
    CandidateProfile,
    CompatibilityReport,
    GapAnalysisReport,
    JobProfile,
    QuestionBank,
)


def merge_dicts(left: dict[str, Any] | None, right: dict[str, Any] | None) -> dict[str, Any]:
    """Reducer for keys written by parallel branches (e.g. ``providers``).

    LangGraph requires an annotated reducer for any channel that can receive
    more than one value per superstep — the resume and job nodes run in
    parallel and both record which provider served them.
    """
    return {**(left or {}), **(right or {})}


class WorkflowState(TypedDict, total=False):
    resume_text: str
    job_text: str
    resume_id: int | None
    job_id: int | None
    candidate: CandidateProfile | None
    job: JobProfile | None
    compatibility: CompatibilityReport | None
    gaps: GapAnalysisReport | None
    questions: QuestionBank | None
    providers: Annotated[dict[str, str], merge_dicts]
    errors: Annotated[list[str], operator.add]
    activity: Annotated[list[dict[str, Any]], operator.add]
    final_report: dict[str, Any]


DEFAULT_STATE: WorkflowState = {
    "resume_text": "",
    "job_text": "",
    "resume_id": None,
    "job_id": None,
    "candidate": None,
    "job": None,
    "compatibility": None,
    "gaps": None,
    "questions": None,
    "providers": {},
    "errors": [],
    "activity": [],
    "final_report": {},
}
