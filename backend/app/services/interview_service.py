"""Interview question generation and deterministic answer evaluation."""
from __future__ import annotations

import re

from ..schemas import (
    AnswerEvaluation,
    CandidateProfile,
    CompatibilityReport,
    InterviewQuestion,
    JobProfile,
    QuestionBank,
)
from .embedding_service import token_overlap
from .skills import skill_template

HR_QUESTIONS = [
    (
        "Tell me about yourself and why you are interested in this role.",
        ["A concise present → past → future structure", "Specific motivation for the role", "One proof point of relevant ability"],
        ["What part of this role excites you most, and why?"],
    ),
    (
        "Why do you want to work at this company?",
        ["Knowledge of the product or mission", "A specific, honest reason", "How your goals align"],
        ["What would you want to learn in your first three months?"],
    ),
    (
        "What is a strength you would bring to this team, with evidence?",
        ["A relevant strength", "Concrete example", "Measurable or observable impact"],
        ["What is a weakness you are actively working on?"],
    ),
    (
        "Where do you see yourself in two to three years?",
        ["Realistic progression", "Alignment with the role", "Learning goals"],
        ["What skills would you need to get there?"],
    ),
]

BEHAVIOURAL_QUESTIONS = [
    (
        "Tell me about a time you handled a difficult deadline. What did you do?",
        ["Situation and constraints", "Prioritisation and communication", "Outcome and what you learned"],
        ["What would you do differently next time?"],
    ),
    (
        "Describe a disagreement with a teammate and how you resolved it.",
        ["The disagreement in concrete terms", "Listening and evidence", "Resolution and relationship"],
        ["How do you handle feedback you disagree with?"],
    ),
    (
        "Tell me about a mistake you made and how you fixed it.",
        ["Ownership without excuses", "Root cause", "Preventive change"],
        ["How do you make sure it does not happen again?"],
    ),
    (
        "Give an example of learning something quickly under pressure.",
        ["The learning goal", "A deliberate method", "The result"],
        ["How do you decide what to learn first?"],
    ),
]

PROBLEM_QUESTIONS = [
    (
        "How would you design a URL shortener from API to storage?",
        ["Requirements and scale assumptions", "Hashing and collision handling", "Storage, caching and analytics trade-offs"],
        ["How would you handle a hot key?"],
    ),
    (
        "Given a list of jobs and resumes, how would you build a ranked matching system?",
        ["Data model and features", "Baseline and evaluation metric", "Failure modes such as keyword stuffing"],
        ["How would you measure whether the ranking is fair?"],
    ),
    (
        "A production endpoint suddenly became slow. Walk me through your debugging process.",
        ["Confirm the symptom with data", "Narrow with logs, metrics and traces", "Fix, verify and prevent recurrence"],
        ["What would you check first if only one region were affected?"],
    ),
]


def generate_question_bank(
    candidate: CandidateProfile | None,
    job: JobProfile,
    compatibility: CompatibilityReport | None = None,
    limit: int = 14,
) -> QuestionBank:
    questions: list[InterviewQuestion] = []
    seen: set[str] = set()

    def add(
        qtype: str,
        text: str,
        why: str,
        points: list[str],
        follow_ups: list[str],
        skill: str = "",
        difficulty: str = "medium",
    ) -> None:
        key = re.sub(r"[^a-z0-9]", "", text.lower())[:80]
        if key in seen or len(questions) >= limit:
            return
        seen.add(key)
        questions.append(
            InterviewQuestion(
                id=f"q{len(questions) + 1}",
                type=qtype,  # type: ignore[arg-type]
                question=text,
                why_asked=why,
                expected_points=points[:5],
                follow_ups=follow_ups[:3],
                difficulty=difficulty,  # type: ignore[arg-type]
                related_skill=skill,
            )
        )

    required = job.required_skills[:8]
    gaps = []
    if compatibility:
        gaps = [m.skill for m in compatibility.missing_skills + compatibility.partially_matched_skills]

    # Warm-up HR questions come first so a truncated bank still opens like a real interview.
    for text, points, follows in HR_QUESTIONS[:2]:
        add("hr", text, "Assesses motivation, self-awareness and fit.", points, follows)

    tech_targets = list(dict.fromkeys(gaps[:3] + required[:5]))
    for skill in tech_targets[:5]:
        template = skill_template(skill)
        for i, question in enumerate(template.questions[:2]):
            add(
                "technical",
                question,
                f"Tests practical understanding of {skill}, which this role requires.",
                template.answer_points + template.topics[:3],
                [
                    f"Can you give a concrete example where {skill} mattered?",
                    f"What is a common mistake people make with {skill}?",
                ],
                skill=skill,
                difficulty="hard" if i == 1 else "medium",
            )

    if candidate:
        for project in candidate.projects[:2]:
            stack = ", ".join(project.technologies[:4]) or "your stack"
            add(
                "project",
                f"Walk me through {project.name}. What problem did it solve, what did you build, and what was the hardest technical decision?",
                "Project questions verify ownership, depth and communication of real work.",
                [
                    "Problem and users",
                    f"Architecture and use of {stack}",
                    "Hardest trade-off and how it was resolved",
                    "Measurable outcome",
                ],
                ["What would you change if you rebuilt it today?", "How did you test it?"],
                skill=stack,
            )

    category = job.role_category
    if category in {"ai_ml", "data", "backend", "frontend", "fullstack", "mobile", "devops", "security", "engineering", "general"}:
        for text, points, follows in PROBLEM_QUESTIONS[:2]:
            add("problem_solving", text, "Assesses structured thinking under ambiguity.", points, follows)

    for text, points, follows in BEHAVIOURAL_QUESTIONS[:2]:
        add("behavioural", text, "Past behaviour is the best available predictor of future behaviour.", points, follows)

    # Ensure a minimum bank even for sparse job descriptions.
    if len(questions) < 6:
        add(
            "hr",
            "Which of your skills best prepares you for this role, and where do you still need to grow?",
            "Checks honest self-assessment against the role.",
            ["Specific strength with evidence", "An honest gap", "A concrete learning plan"],
            ["How are you closing that gap this month?"],
        )
    return QuestionBank(questions=questions)


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+|\n+", text or "") if s.strip()]


def evaluate_answer(
    question: InterviewQuestion,
    answer: str,
    candidate: CandidateProfile | None = None,
) -> AnswerEvaluation:
    answer = (answer or "").strip()
    words = re.findall(r"[A-Za-z0-9+#.']+", answer)
    word_count = len(words)
    lower = answer.lower()

    overlap = token_overlap(answer, question.expected_points) if question.expected_points else 0.0
    if not answer:
        return AnswerEvaluation(
            overall=0,
            feedback="No answer was submitted. In a real interview, say what you know and state your assumptions rather than staying silent.",
            suggestions=["Answer with a structure: context → approach → trade-off → result.", "Rehearse a 60–90 second answer aloud."],
        )

    length_factor = min(1.0, word_count / 70)
    example = 1.0 if re.search(r"\b(for example|in my project|i built|i worked|at my|when i)\b", lower) else 0.0
    structure = sum(
        1 for marker in ("first", "then", "because", "trade-off", "tradeoff", "however", "as a result", "so that")
        if marker in lower
    ) / 4
    filler = sum(lower.count(f) for f in ("um", "uh", "like i said", "basically", "stuff", "things")) / max(1, word_count / 60)
    technical = min(100.0, 15 + overlap * 75 + example * 10)
    conceptual = min(100.0, 10 + overlap * 65 + length_factor * 25)
    communication = max(10.0, min(100.0, 45 + length_factor * 35 + min(1, structure) * 20 - filler * 10))
    problem = min(100.0, 15 + structure * 55 + example * 20 + overlap * 10)
    relevance = min(100.0, 10 + overlap * 80 + (10 if question.related_skill and question.related_skill.lower() in lower else 0))
    completeness = min(100.0, 10 + overlap * 55 + length_factor * 35)
    if word_count < 12:
        technical *= 0.6
        conceptual *= 0.6
        completeness *= 0.5

    scores = {
        "technical_accuracy": round(technical, 0),
        "conceptual_understanding": round(conceptual, 0),
        "communication": round(communication, 0),
        "problem_solving": round(problem, 0),
        "relevance": round(relevance, 0),
        "completeness": round(completeness, 0),
    }
    overall = round(
        technical * 0.25
        + conceptual * 0.20
        + communication * 0.15
        + problem * 0.15
        + relevance * 0.15
        + completeness * 0.10,
        1,
    )

    weak_dimension = min(
        [
            ("technical accuracy", technical),
            ("conceptual understanding", conceptual),
            ("communication", communication),
            ("problem solving", problem),
            ("relevance", relevance),
            ("completeness", completeness),
        ],
        key=lambda item: item[1],
    )[0]

    if overall >= 80:
        feedback = "Strong answer: it is relevant, specific and shows structured reasoning. Keep the same level of detail."
    elif overall >= 60:
        feedback = (
            f"Solid answer with room to sharpen {weak_dimension}. Add one concrete example and state the trade-off explicitly."
        )
    elif overall >= 40:
        feedback = (
            f"Partially addresses the question. The main weakness is {weak_dimension}; the answer needs more specific evidence."
        )
    else:
        feedback = (
            f"The answer does not yet address the core of the question. Focus on {weak_dimension}: "
            "name the concept, give a concrete example, and explain the outcome."
        )

    suggestions: list[str] = []
    if word_count < 40:
        suggestions.append("Expand to roughly 60–120 words: context, action, result.")
    if overlap < 0.4 and question.expected_points:
        suggestions.append("Cover these expected points: " + "; ".join(question.expected_points[:3]) + ".")
    if example == 0:
        suggestions.append("Include a specific example from a project, internship or coursework.")
    if structure < 0.5:
        suggestions.append("Signpost your reasoning: first…, because…, the trade-off is…, as a result….")
    if filler > 1:
        suggestions.append("Remove filler words and pause briefly instead.")
    if not suggestions:
        suggestions.append("Tighten the ending with a one-sentence summary of the result.")

    follow_up = ""
    if overall < 58 and question.follow_ups:
        follow_up = question.follow_ups[0]

    return AnswerEvaluation(
        **scores,
        overall=overall,
        feedback=feedback,
        suggestions=suggestions[:4],
        follow_up=follow_up,
    )


def build_final_report(evaluations: list[AnswerEvaluation], candidate: CandidateProfile | None = None):
    from ..schemas import InterviewReport

    if not evaluations:
        return InterviewReport(
            overall_performance=0,
            readiness="not assessed",
            summary="No answers were evaluated. Complete at least one question to receive a report.",
        )
    dims = [
        "technical_accuracy",
        "conceptual_understanding",
        "communication",
        "problem_solving",
        "relevance",
        "completeness",
    ]
    averages = {d: round(sum(getattr(e, d) for e in evaluations) / len(evaluations), 1) for d in dims}
    overall = round(sum(e.overall for e in evaluations) / len(evaluations), 1)
    strongest = max(averages, key=averages.get)
    weakest = min(averages, key=averages.get)
    readiness = "interview-ready" if overall >= 75 else "nearly ready" if overall >= 55 else "needs preparation"
    summary = (
        f"You completed {len(evaluations)} evaluated answer(s) with an average score of {overall:.0f}/100. "
        f"Your strongest dimension is {strongest.replace('_', ' ')} ({averages[strongest]:.0f}) and the biggest "
        f"opportunity is {weakest.replace('_', ' ')} ({averages[weakest]:.0f})."
    )
    strengths = [
        f"{k.replace('_', ' ').title()}: {v:.0f}/100"
        for k, v in averages.items()
        if v >= 65
    ] or ["You completed the session — consistency is the first win."]
    improvement = [
        f"{k.replace('_', ' ').title()}: {v:.0f}/100"
        for k, v in averages.items()
        if v < 60
    ] or ["No dimension is critically weak; now increase specificity and depth."]
    recommendations = [
        f"Practise the {weakest.replace('_', ' ')} dimension with two more answers this week.",
        "Prepare three quantified project stories you can adapt to behavioural questions.",
        "Record one answer and remove filler words and unsupported claims.",
    ]
    return InterviewReport(
        overall_performance=overall,
        readiness=readiness,
        summary=summary,
        strengths=strengths,
        improvement_areas=improvement,
        recommendations=recommendations,
        answered_questions=len(evaluations),
    )
