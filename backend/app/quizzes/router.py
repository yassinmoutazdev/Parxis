"""Quiz API router.

Corresponds to ARCHITECTURE Section 6.3 (sequence diagram) and PRD Section 10 (Flow 2).
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db.models.quiz import QuizMode, QuizScope
from app.llm.ollama_adapter import reraise_known_ollama_error
from app.quizzes.service import QuizService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/quizzes", tags=["quizzes"])


class StartQuizRequest(BaseModel):
    """Request body for starting a quiz session.

    Note: 'mode' field is deprecated and ignored. All quizzes are MULTIPLE_CHOICE.
    """

    size: int = 10
    scope: QuizScope = QuizScope.AD_HOC
    week_id: int | None = None


class QuizQuestionResponse(BaseModel):
    """Response for a quiz question."""

    id: int
    question_type: QuizMode
    prompt: str
    correct_answer: str | None = None  # Not sent to frontend for obvious reasons
    options: list[str] | None = None


class QuizSessionResponse(BaseModel):
    """Response for a quiz session."""

    id: int
    quiz_scope: QuizScope
    quiz_mode: QuizMode
    started_at: str
    completed_at: str | None = None
    questions: list[QuizQuestionResponse]


class SubmitAnswerRequest(BaseModel):
    """Request body for submitting quiz answers."""

    answers: dict[int, str]  # question_id -> user_answer


class GradedQuestionResponse(BaseModel):
    """Response for a graded quiz question."""

    id: int
    question_type: QuizMode
    prompt: str
    user_answer: str | None
    is_correct: bool | None
    score: float | None
    feedback: str | None
    graded_by: str | None
    options: list[str] | None = None


class SessionSummaryResponse(BaseModel):
    """Response for a completed quiz session."""

    id: int
    quiz_scope: QuizScope
    quiz_mode: QuizMode
    started_at: str
    completed_at: str | None
    total_questions: int
    correct_count: int
    incorrect_count: int
    questions: list[GradedQuestionResponse]


@router.post("", response_model=QuizSessionResponse)
async def start_quiz(request: StartQuizRequest) -> QuizSessionResponse:
    """Start a new quiz session.

    ARCHITECTURE Section 6.3:
    - POST /quizzes { size } - synchronous per ADR-08
    - Returns QuizSession + QuizQuestion[] (prompts only, no answers)

    Args:
        request: Quiz start request with size, scope, etc.

    Returns:
        QuizSessionResponse with session info and questions

    Raises:
        HTTPException: If quiz generation fails
    """
    try:
        session, questions = await QuizService.start_session(
            size=request.size,
            scope=request.scope,
            week_id=request.week_id,
        )

        return QuizSessionResponse(
            id=session.id,
            quiz_scope=session.quiz_scope,
            quiz_mode=session.quiz_mode,
            started_at=session.started_at.isoformat(),
            completed_at=session.completed_at.isoformat() if session.completed_at else None,
            questions=[
                QuizQuestionResponse(
                    id=q.id,
                    question_type=q.question_type,
                    prompt=q.prompt,
                    correct_answer=None,  # Don't send correct answer to frontend
                    options=q.options_json,
                )
                for q in questions
            ],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        reraise_known_ollama_error(e)
        logger.error(f"Failed to start quiz: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate quiz")


@router.post("/{session_id}/answers", response_model=SessionSummaryResponse)
async def submit_answers(
    session_id: int, request: SubmitAnswerRequest
) -> SessionSummaryResponse:
    """Submit answers for a quiz session and get grading results.

    ARCHITECTURE Section 6.3:
    - POST /quizzes/{session_id}/answers { question_id, user_answer }[]
    - Returns session summary with graded results

    Args:
        session_id: The quiz session ID
        request: Answers mapping question_id to user_answer

    Returns:
        SessionSummaryResponse with grading results

    Raises:
        HTTPException: If session not found or grading fails
    """
    try:
        session = await QuizService.grade_session(
            session_id=session_id,
            answers=request.answers,
        )

        # Get updated questions with grades
        _, questions = QuizService.get_session_with_questions(session_id)

        correct_count = sum(1 for q in questions if q.is_correct)
        incorrect_count = len(questions) - correct_count

        return SessionSummaryResponse(
            id=session.id,
            quiz_scope=session.quiz_scope,
            quiz_mode=session.quiz_mode,
            started_at=session.started_at.isoformat(),
            completed_at=session.completed_at.isoformat() if session.completed_at else None,
            total_questions=len(questions),
            correct_count=correct_count,
            incorrect_count=incorrect_count,
            questions=[
                GradedQuestionResponse(
                    id=q.id,
                    question_type=q.question_type,
                    prompt=q.prompt,
                    user_answer=q.user_answer,
                    is_correct=q.is_correct,
                    score=q.score,
                    feedback=q.feedback,
                    graded_by=q.graded_by.value if q.graded_by else None,
                    options=q.options_json,
                )
                for q in questions
            ],
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        reraise_known_ollama_error(e)
        logger.error(f"Failed to grade quiz: {e}")
        raise HTTPException(status_code=500, detail="Failed to grade quiz")


@router.get("/{session_id}", response_model=SessionSummaryResponse)
async def get_session(session_id: int) -> SessionSummaryResponse:
    """Get a quiz session summary.

    Args:
        session_id: The quiz session ID

    Returns:
        SessionSummaryResponse with session and question data

    Raises:
        HTTPException: If session not found
    """
    try:
        session, questions = QuizService.get_session_with_questions(session_id)

        correct_count = sum(1 for q in questions if q.is_correct)
        incorrect_count = sum(1 for q in questions if q.is_correct is False)

        return SessionSummaryResponse(
            id=session.id,
            quiz_scope=session.quiz_scope,
            quiz_mode=session.quiz_mode,
            started_at=session.started_at.isoformat(),
            completed_at=session.completed_at.isoformat() if session.completed_at else None,
            total_questions=len(questions),
            correct_count=correct_count,
            incorrect_count=incorrect_count,
            questions=[
                GradedQuestionResponse(
                    id=q.id,
                    question_type=q.question_type,
                    prompt=q.prompt,
                    user_answer=q.user_answer,
                    is_correct=q.is_correct,
                    score=q.score,
                    feedback=q.feedback,
                    graded_by=q.graded_by.value if q.graded_by else None,
                    options=q.options_json,
                )
                for q in questions
            ],
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
