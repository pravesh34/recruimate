"""Interview preparation, mock interview state machine and history."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..agents.interview_agent import InterviewAgent
from ..database.models import (
    CompatibilityReport,
    InterviewEvaluation,
    InterviewMessage,
    InterviewSession,
    JobAnalysis,
    ResumeProfile,
    get_db,
)
from ..gateway import GatewayManager
from ..schemas import (
    AnswerEvaluation,
    CandidateProfile,
    CompatibilityReport as CompatibilitySchema,
    InterviewQuestion,
    JobProfile,
)
from ..services.interview_service import build_final_report
from .deps import get_current_user, get_gateway, iso
from .schemas import InterviewAnswerRequest, InterviewCreateRequest, InterviewPrepRequest

router = APIRouter(prefix="/api/interviews", tags=["interviews"])


def _compat(
    db: Session, compatibility_id: int | None, user
) -> CompatibilityReport:
    record = (
        db.get(CompatibilityReport, compatibility_id)
        if compatibility_id
        else db.query(CompatibilityReport)
        .filter(CompatibilityReport.user_id == user.id)
        .order_by(CompatibilityReport.created_at.desc(), CompatibilityReport.id.desc())
        .first()
    )
    if not record or record.user_id != user.id:
        raise HTTPException(404, "Run a compatibility analysis first.")
    return record


def _profiles(db: Session, compatibility: CompatibilityReport):
    resume = db.get(ResumeProfile, compatibility.resume_id)
    job = db.get(JobAnalysis, compatibility.job_id)
    candidate = CandidateProfile.model_validate((resume.profile if resume else {}) or {})
    job_profile = JobProfile.model_validate((job.profile if job else {}) or {})
    report = CompatibilitySchema.model_validate(compatibility.report or {})
    return candidate, job_profile, report


def _public_question(question: dict) -> dict:
    return {
        "id": question.get("id", ""),
        "type": question.get("type", "technical"),
        "question": question.get("question", ""),
        "why_asked": question.get("why_asked", ""),
        "difficulty": question.get("difficulty", "medium"),
        "related_skill": question.get("related_skill", ""),
    }


def session_to_dict(session: InterviewSession, include_state: bool = False) -> dict:
    state = session.state or {}
    questions = state.get("questions", [])
    index = int(state.get("index", 0))
    current = questions[index] if 0 <= index < len(questions) and session.status == "active" else None
    messages = [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "meta": m.meta or {},
            "created_at": iso(m.created_at),
        }
        for m in sorted(session.messages, key=lambda m: m.id)
    ]
    evaluations = [
        {
            "id": e.id,
            "question": e.question,
            "answer": e.answer,
            "scores": e.scores,
            "feedback": e.feedback,
            "suggestions": e.suggestions,
            "created_at": iso(e.created_at),
        }
        for e in sorted(session.evaluations, key=lambda e: e.id)
    ]
    data = {
        "id": session.id,
        "role": session.role,
        "status": session.status,
        "kind": session.kind,
        "provider": session.provider,
        "compatibility_id": session.compatibility_id,
        "report": session.report or {},
        "messages": messages,
        "evaluations": evaluations,
        "current_question": _public_question(current) if current else None,
        "progress": {
            "answered": int(state.get("answered", 0)),
            "total": int(state.get("max_questions", len(questions))),
            "percent": round(
                min(100.0, int(state.get("answered", 0)) / max(1, int(state.get("max_questions", len(questions)))) * 100),
                1,
            ),
        },
        "created_at": iso(session.created_at),
        "updated_at": iso(session.updated_at),
    }
    if include_state:
        data["state"] = state
    return data


def _add_message(session: InterviewSession, role: str, content: str, meta: dict | None = None):
    message = InterviewMessage(session_id=session.id, role=role, content=content, meta=meta or {})
    session.messages.append(message)
    return message


def _order_for_interview(questions: list, limit: int) -> list:
    """Run the mock like a real interview: warm-up, project, then depth."""
    buckets: dict[str, list] = {key: [] for key in ("hr", "project", "technical", "behavioural", "problem_solving")}
    for question in questions:
        buckets.setdefault(question.type, []).append(question)
    ordered: list = []

    def _as_dict(question):
        dump = getattr(question, "model_dump", None)
        return dump() if callable(dump) else dict(question)

    def take(qtype: str) -> None:
        if buckets.get(qtype) and len(ordered) < limit:
            ordered.append(_as_dict(buckets[qtype].pop(0)))

    take("hr")
    take("project")
    while len(ordered) < limit:
        before = len(ordered)
        for qtype in ("technical", "project", "behavioural", "problem_solving", "hr"):
            take(qtype)
        if len(ordered) == before:
            break
    return ordered


@router.post("/prep")
async def interview_prep(
    payload: InterviewPrepRequest,
    db: Session = Depends(get_db),
    gateway: GatewayManager = Depends(get_gateway),
    user=Depends(get_current_user),
):
    compatibility = _compat(db, payload.compatibility_id, user)
    candidate, job, report = _profiles(db, compatibility)
    bank, provider, warning = await InterviewAgent(gateway).build_question_bank(
        candidate, job, report, limit=payload.limit
    )
    return {
        "compatibility_id": compatibility.id,
        "job_title": job.job_title,
        "provider": provider,
        "questions": [q.model_dump() for q in bank.questions],
        "warning": warning,
    }


@router.post("")
async def create_interview(
    payload: InterviewCreateRequest,
    db: Session = Depends(get_db),
    gateway: GatewayManager = Depends(get_gateway),
    user=Depends(get_current_user),
):
    compatibility = _compat(db, payload.compatibility_id, user)
    candidate, job, report = _profiles(db, compatibility)
    bank, provider, warning = await InterviewAgent(gateway).build_question_bank(
        candidate, job, report, limit=max(payload.question_limit, 6)
    )
    questions = _order_for_interview(bank.questions, payload.question_limit)
    if not questions:
        raise HTTPException(422, "Could not generate interview questions for this role.")

    session = InterviewSession(
        user_id=user.id,
        compatibility_id=compatibility.id,
        role=payload.role or job.job_title or "Target role",
        status="active",
        kind=payload.kind,
        provider=provider,
        state={
            "questions": questions,
            "index": 0,
            "follow_up_used": False,
            "answered": 0,
            "max_questions": len(questions),
            "question_limit": payload.question_limit,
        },
    )
    db.add(session)
    db.flush()
    first = questions[0]
    _add_message(
        session,
        "assistant",
        (
            f"Welcome. I'll run a short mock interview for **{session.role}**. "
            "I will ask one question at a time and give feedback at the end. "
            "Answer as you would in a real interview; it's fine to state assumptions."
        ),
        {"kind": "intro"},
    )
    _add_message(
        session,
        "assistant",
        first["question"],
        {"kind": "question", "question_id": first.get("id"), "type": first.get("type")},
    )
    db.commit()
    db.refresh(session)
    return {**session_to_dict(session), "warning": warning}


@router.post("/{interview_id}/answer")
async def answer_interview(
    interview_id: int,
    payload: InterviewAnswerRequest,
    db: Session = Depends(get_db),
    gateway: GatewayManager = Depends(get_gateway),
    user=Depends(get_current_user),
):
    session = db.get(InterviewSession, interview_id)
    if not session or session.user_id != user.id:
        raise HTTPException(404, "Interview session not found.")
    if session.status != "active":
        raise HTTPException(409, "This interview is already complete.")
    answer = (payload.answer or "").strip()
    if not answer:
        raise HTTPException(400, "Write an answer before submitting.")
    state = dict(session.state or {})
    questions = state.get("questions", [])
    index = int(state.get("index", 0))
    if index >= len(questions):
        raise HTTPException(409, "No question is pending.")
    question_data = questions[index]
    question = InterviewQuestion.model_validate(question_data)

    compatibility = db.get(CompatibilityReport, session.compatibility_id) if session.compatibility_id else None
    candidate = CandidateProfile.model_validate(
        (db.get(ResumeProfile, compatibility.resume_id).profile if compatibility else {}) or {}
    )
    agent = InterviewAgent(gateway)
    evaluation, provider = await agent.evaluate(question, answer, candidate)

    _add_message(session, "candidate", answer, {"kind": "answer", "question_id": question.id})
    db.add(
        InterviewEvaluation(
            session_id=session.id,
            question=question.question,
            answer=answer,
            scores={
                "technical_accuracy": evaluation.technical_accuracy,
                "conceptual_understanding": evaluation.conceptual_understanding,
                "communication": evaluation.communication,
                "problem_solving": evaluation.problem_solving,
                "relevance": evaluation.relevance,
                "completeness": evaluation.completeness,
                "overall": evaluation.overall,
            },
            feedback=evaluation.feedback,
            suggestions=evaluation.suggestions,
        )
    )
    session.provider = provider
    state["answered"] = int(state.get("answered", 0)) + 1

    completed = False
    if evaluation.follow_up and not state.get("follow_up_used"):
        state["follow_up_used"] = True
        _add_message(
            session,
            "assistant",
            evaluation.follow_up,
            {"kind": "follow_up", "question_id": question.id},
        )
    else:
        state["follow_up_used"] = False
        state["index"] = index + 1
        if state["index"] >= len(questions) or state["answered"] >= int(state.get("max_questions", len(questions))):
            completed = True
        else:
            nxt = questions[state["index"]]
            _add_message(
                session,
                "assistant",
                nxt["question"],
                {"kind": "question", "question_id": nxt.get("id"), "type": nxt.get("type")},
            )

    session.state = state
    db.commit()
    db.refresh(session)

    if completed:
        evaluations = [
            AnswerEvaluation(
                **{
                    k: v
                    for k, v in (e.scores or {}).items()
                    if k
                    in {
                        "technical_accuracy",
                        "conceptual_understanding",
                        "communication",
                        "problem_solving",
                        "relevance",
                        "completeness",
                        "overall",
                    }
                },
                feedback=e.feedback,
                suggestions=e.suggestions or [],
            )
            for e in session.evaluations
        ]
        report = build_final_report(evaluations, candidate)
        session.report = report.model_dump()
        session.status = "completed"
        _add_message(
            session,
            "assistant",
            (
                f"That completes the interview. Average score: **{report.overall_performance:.0f}/100** "
                f"({report.readiness}). Open the report tab for strengths and next steps."
            ),
            {"kind": "summary"},
        )
        db.commit()
        db.refresh(session)

    return {
        "session": session_to_dict(session),
        "evaluation": evaluation.model_dump(),
        "next_question": session_to_dict(session)["current_question"],
        "completed": completed,
    }


@router.post("/{interview_id}/complete")
def complete_interview(
    interview_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    session = db.get(InterviewSession, interview_id)
    if not session or session.user_id != user.id:
        raise HTTPException(404, "Interview session not found.")
    evaluations = [
        AnswerEvaluation(
            **{
                k: v
                for k, v in (e.scores or {}).items()
                if k
                in {
                    "technical_accuracy",
                    "conceptual_understanding",
                    "communication",
                    "problem_solving",
                    "relevance",
                    "completeness",
                    "overall",
                }
            },
            feedback=e.feedback,
            suggestions=e.suggestions or [],
        )
        for e in session.evaluations
    ]
    report = build_final_report(evaluations)
    session.report = report.model_dump()
    session.status = "completed"
    db.commit()
    db.refresh(session)
    return session_to_dict(session)


@router.get("")
def list_interviews(db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = (
        db.query(InterviewSession)
        .filter(InterviewSession.user_id == user.id)
        .order_by(InterviewSession.created_at.desc(), InterviewSession.id.desc())
        .limit(30)
        .all()
    )
    return [
        {
            "id": s.id,
            "role": s.role,
            "status": s.status,
            "kind": s.kind,
            "score": (s.report or {}).get("overall_performance", 0),
            "answered": (s.state or {}).get("answered", 0),
            "created_at": iso(s.created_at),
        }
        for s in rows
    ]


@router.get("/{interview_id}")
def get_interview(
    interview_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    session = db.get(InterviewSession, interview_id)
    if not session or session.user_id != user.id:
        raise HTTPException(404, "Interview session not found.")
    return session_to_dict(session)


@router.delete("/{interview_id}")
def delete_interview(
    interview_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    session = db.get(InterviewSession, interview_id)
    if not session or session.user_id != user.id:
        raise HTTPException(404, "Interview session not found.")
    db.delete(session)
    db.commit()
    return {"deleted": True, "id": interview_id}
