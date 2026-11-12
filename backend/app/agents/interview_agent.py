"""Agent 5 — Interview Preparation and mock-interview evaluation."""
from __future__ import annotations

from ..prompts import EVALUATE_SYSTEM, EVALUATE_USER, QUESTIONS_SYSTEM, QUESTIONS_USER
from ..schemas import (
    AnswerEvaluation,
    CandidateProfile,
    CompatibilityReport,
    InterviewQuestion,
    JobProfile,
    QuestionBank,
)
from ..services.interview_service import evaluate_answer, generate_question_bank
from .base import BaseAgent


class InterviewAgent(BaseAgent):
    name = "interview_agent"
    label = "Interview Preparation"

    async def build_question_bank(
        self,
        candidate: CandidateProfile | None,
        job: JobProfile,
        compatibility: CompatibilityReport | None = None,
        limit: int = 14,
    ) -> tuple[QuestionBank, str, str]:
        baseline = generate_question_bank(candidate, job, compatibility, limit=limit)
        if not self.llm_enabled:
            return baseline, "heuristic", ""
        gaps = ""
        if compatibility:
            gaps = ", ".join(
                m.skill for m in compatibility.missing_skills + compatibility.partially_matched_skills
            )
        prompt = QUESTIONS_USER.format(
            job_title=job.job_title,
            role_category=job.role_category,
            required_skills=", ".join(job.required_skills[:15]),
            preferred_skills=", ".join(job.preferred_skills[:10]),
            responsibilities="; ".join(job.responsibilities[:6]),
            candidate_skills=", ".join((candidate.skills if candidate else [])[:20]),
            projects="; ".join(
                f"{p.name} ({', '.join(p.technologies[:4])})" for p in (candidate.projects if candidate else [])[:4]
            ),
            gaps=gaps,
        )
        llm_bank, provider, error = await self._generate(
            prompt, QuestionBank, system=QUESTIONS_SYSTEM, temperature=0.4, max_tokens=3000
        )
        if not llm_bank or len(llm_bank.questions) < 5:
            return baseline, provider, error
        # Re-number ids to keep the mock state machine stable.
        for i, question in enumerate(llm_bank.questions, start=1):
            question.id = f"q{i}"
        return llm_bank, provider, error

    async def evaluate(
        self,
        question: InterviewQuestion,
        answer: str,
        candidate: CandidateProfile | None = None,
    ) -> tuple[AnswerEvaluation, str]:
        baseline = evaluate_answer(question, answer, candidate)
        if not self.llm_enabled or not answer.strip():
            return baseline, "heuristic"
        prompt = EVALUATE_USER.format(
            question=question.question,
            expected_points="; ".join(question.expected_points),
            answer=answer[:6000],
        )
        llm_eval, provider, _ = await self._generate(
            prompt, AnswerEvaluation, system=EVALUATE_SYSTEM, temperature=0.1, max_tokens=1200
        )
        if not llm_eval:
            return baseline, provider
        # Blend deterministically computed dimensions with the LLM judgement, and
        # always recompute the weighted overall so it cannot be arbitrary.
        for dimension in (
            "technical_accuracy",
            "conceptual_understanding",
            "communication",
            "problem_solving",
            "relevance",
            "completeness",
        ):
            llm_value = float(getattr(llm_eval, dimension) or 0)
            base_value = float(getattr(baseline, dimension) or 0)
            setattr(llm_eval, dimension, round(0.6 * llm_value + 0.4 * base_value, 1))
        llm_eval.overall = round(
            llm_eval.technical_accuracy * 0.25
            + llm_eval.conceptual_understanding * 0.20
            + llm_eval.communication * 0.15
            + llm_eval.problem_solving * 0.15
            + llm_eval.relevance * 0.15
            + llm_eval.completeness * 0.10,
            1,
        )
        if not llm_eval.suggestions:
            llm_eval.suggestions = baseline.suggestions
        if not llm_eval.feedback:
            llm_eval.feedback = baseline.feedback
        return llm_eval, provider
