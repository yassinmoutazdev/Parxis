"""Reports API router.

Corresponds to ARCHITECTURE Section 6.5 (Weekly Report Assembly sequence).
"""

import logging
from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db.models.quiz import QuizScope
from app.quizzes.service import QuizService
from app.reports.service import ReportService
from app.writing.service import WritingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reports", tags=["reports"])


class WeeklyReportResponse(BaseModel):
    """Response for a weekly report."""

    id: int
    week_start: str
    week_end: str
    items_studied_count: int
    quiz_summary_json: dict[str, Any] | None
    mini_writing_summary_json: dict[str, Any] | None
    weekly_writing_evaluation_id: int | None
    mastery_snapshot_json: dict[str, Any] | None
    narrative_report: str | None
    created_at: str


class ReportListResponse(BaseModel):
    """Response for listing reports."""

    reports: list[WeeklyReportResponse]


class FinalizeReportRequest(BaseModel):
    """Request body for finalizing a weekly report."""

    week_start: str | None = None
    week_end: str | None = None


class StartWeeklyReviewResponse(BaseModel):
    """Response for starting a weekly review."""

    week_start: str
    week_end: str
    existing_report_id: int | None = None


def _report_to_response(report) -> WeeklyReportResponse:
    """Convert a WeeklyReport to response format."""
    return WeeklyReportResponse(
        id=report.id,
        week_start=str(report.week_start),
        week_end=str(report.week_end),
        items_studied_count=report.items_studied_count,
        quiz_summary_json=report.quiz_summary_json,
        mini_writing_summary_json=report.mini_writing_summary_json,
        weekly_writing_evaluation_id=report.weekly_writing_evaluation_id,
        mastery_snapshot_json=report.mastery_snapshot_json,
        narrative_report=report.narrative_report,
        created_at=report.created_at.isoformat(),
    )


@router.post("/weekly/start", response_model=StartWeeklyReviewResponse)
async def start_weekly_review() -> StartWeeklyReviewResponse:
    """Start a weekly review.

    Returns the current week's boundary dates.
    If a report already exists for this week, returns its ID.

    Returns:
        StartWeeklyReviewResponse with week boundaries
    """
    try:
        week_start, week_end = ReportService.get_week_boundary()

        # Check if report already exists for this week
        existing = ReportService.get_report_by_week(week_start)

        return StartWeeklyReviewResponse(
            week_start=str(week_start),
            week_end=str(week_end),
            existing_report_id=existing.id if existing else None,
        )
    except Exception as e:
        logger.error(f"Failed to start weekly review: {e}")
        raise HTTPException(status_code=500, detail="Failed to start weekly review")


@router.post("/weekly/quiz")
async def start_weekly_quiz() -> dict:
    """Start a weekly quiz session.

    Delegates to QuizService with quiz_scope=WEEKLY_REVIEW.
    Weekly quiz uses a larger size (15) and biases toward items
    studied/reviewed in the current week.

    Returns:
        Quiz session and questions
    """
    try:
        # Get current week start for scope-aware retrieval
        from datetime import date
        week_start, _ = ReportService.get_week_boundary()

        # Start a quiz with weekly review scope
        session, questions = await QuizService.start_session(
            size=15,  # Larger size for weekly quiz
            scope=QuizScope.WEEKLY_REVIEW,
            since=week_start,
        )

        return {
            "session_id": session.id,
            "questions": [
                {
                    "id": q.id,
                    "question_type": q.question_type.value,
                    "prompt": q.prompt,
                }
                for q in questions
            ],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to start weekly quiz: {e}")
        raise HTTPException(status_code=500, detail="Failed to start weekly quiz")


@router.post("/weekly/writing-prompt")
async def create_weekly_writing_prompt() -> dict:
    """Create a weekly writing prompt.

    Delegates to WritingService.generate_weekly_prompt().

    Returns:
        Writing prompt
    """
    try:
        prompt = WritingService.generate_weekly_prompt()
        return {
            "id": prompt.id,
            "prompt_type": prompt.prompt_type.value,
            "topic": prompt.topic,
            "used_at": prompt.used_at.isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to create weekly writing prompt: {e}")
        raise HTTPException(status_code=500, detail="Failed to create writing prompt")


@router.post("/weekly/writing-submit")
async def submit_weekly_writing(request: dict) -> dict:
    """Submit and evaluate weekly writing.

    Delegates to WritingService.submit_and_evaluate().

    Request body:
        prompt_id: int
        text: str

    Returns:
        Submission and evaluation
    """
    try:
        prompt_id = request.get("prompt_id")
        text = request.get("text")

        if not prompt_id or not text:
            raise HTTPException(status_code=400, detail="prompt_id and text required")

        submission, evaluation = await WritingService.submit_and_evaluate(
            prompt_id=prompt_id,
            text=text,
        )

        return {
            "submission": {
                "id": submission.id,
                "prompt_id": submission.prompt_id,
                "submission_type": submission.submission_type.value,
                "submitted_text": submission.submitted_text,
                "word_count": submission.word_count,
                "created_at": submission.created_at.isoformat(),
            },
            "evaluation": {
                "id": evaluation.id,
                "grammar_score": evaluation.grammar_score,
                "naturalness_score": evaluation.naturalness_score,
                "vocabulary_score": evaluation.vocabulary_score,
                "coherence_score": evaluation.coherence_score,
                "overall_score": evaluation.overall_score,
                "feedback_json": evaluation.feedback_json,
            },
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to submit weekly writing: {e}")
        raise HTTPException(status_code=500, detail="Failed to evaluate writing")


@router.post("/weekly/finalize", response_model=WeeklyReportResponse)
async def finalize_weekly_report(
    request: FinalizeReportRequest,
) -> WeeklyReportResponse:
    """Finalize the weekly report.

    ARCHITECTURE Section 6.5:
    - POST /reports/weekly/finalize { week_start, week_end }
    - Calls ReportService.assemble()
    - Returns the full WeeklyReport

    Args:
        request: Finalize request with optional week boundaries

    Returns:
        WeeklyReportResponse with full report data
    """
    try:
        # Parse dates if provided
        week_start = None
        week_end = None

        if request.week_start:
            week_start = date.fromisoformat(request.week_start)
        if request.week_end:
            week_end = date.fromisoformat(request.week_end)

        # Assemble the report
        report = await ReportService.assemble(
            week_start=week_start,
            week_end=week_end,
        )

        return _report_to_response(report)

    except Exception as e:
        logger.error(f"Failed to finalize weekly report: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate report")


@router.get("", response_model=ReportListResponse)
async def list_reports(limit: int = 10) -> ReportListResponse:
    """List weekly reports.

    Args:
        limit: Maximum number of reports to return

    Returns:
        ReportListResponse with reports
    """
    try:
        reports = ReportService.get_reports(limit=limit)
        return ReportListResponse(
            reports=[_report_to_response(r) for r in reports]
        )
    except Exception as e:
        logger.error(f"Failed to list reports: {e}")
        raise HTTPException(status_code=500, detail="Failed to list reports")


@router.get("/weekly/{report_id}", response_model=WeeklyReportResponse)
async def get_report(report_id: int) -> WeeklyReportResponse:
    """Get a weekly report by ID.

    Args:
        report_id: The report ID

    Returns:
        WeeklyReportResponse with report data
    """
    report = ReportService.get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    return _report_to_response(report)
