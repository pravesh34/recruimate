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
    providers: dict[str, str]
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
