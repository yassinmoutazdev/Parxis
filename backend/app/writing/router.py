"""Writing API router.

Corresponds to ARCHITECTURE Section 6.4 (Weekly Writing Assessment sequence).
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db.models.writing import WritingPromptType
from app.llm.ollama_adapter import reraise_known_ollama_error
from app.writing.service import WritingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/writing", tags=["writing"])


class WritingPromptResponse(BaseModel):
    """Response for a writing prompt."""

    id: int
    prompt_type: str
    topic: str
    used_at: str


class SubmitWritingRequest(BaseModel):
    """Request body for submitting a writing."""

    prompt_id: int
    text: str


class WritingSubmissionResponse(BaseModel):
    """Response for a writing submission."""

    id: int
    prompt_id: int
    submission_type: str
    submitted_text: str
    word_count: int
    created_at: str


class WritingEvaluationResponse(BaseModel):
    """Response for a writing evaluation."""

    id: int
    submission_id: int
    grammar_score: float | None
    naturalness_score: float | None
    vocabulary_score: float | None
    coherence_score: float | None
    overall_score: float | None
    feedback_json: dict[str, Any] | None
    suggested_items_json: list[dict[str, Any]] | None
    evaluator_provider: str | None
    evaluator_model: str | None
    prompt_version: str | None
    rubric_version: str | None
    created_at: str


class WritingSubmitResponse(BaseModel):
    """Response for a writing submission with evaluation."""

    submission: WritingSubmissionResponse
    evaluation: WritingEvaluationResponse


class PromptListResponse(BaseModel):
    """Response for listing prompts."""

    prompts: list[WritingPromptResponse]


@router.post("/prompts/mini", response_model=WritingPromptResponse)
async def create_mini_prompt() -> WritingPromptResponse:
    """Create a mini writing prompt.

    Returns:
        WritingPromptResponse with prompt details
    """
    try:
        prompt = WritingService.generate_mini_prompt()
        return WritingPromptResponse(
            id=prompt.id,
            prompt_type=prompt.prompt_type.value,
            topic=prompt.topic,
            used_at=prompt.used_at.isoformat(),
        )
    except Exception as e:
        reraise_known_ollama_error(e)
        logger.error(f"Failed to create mini prompt: {e}")
        raise HTTPException(status_code=500, detail="Failed to create prompt")


@router.post("/prompts/weekly", response_model=WritingPromptResponse)
async def create_weekly_prompt() -> WritingPromptResponse:
    """Create a weekly writing prompt.

    ARCHITECTURE Section 6.4:
    - POST /writing/prompts/weekly → generate_weekly_prompt() with fuzzy-match retry

    Returns:
        WritingPromptResponse with prompt details
    """
    try:
        prompt = WritingService.generate_weekly_prompt()
        return WritingPromptResponse(
            id=prompt.id,
            prompt_type=prompt.prompt_type.value,
            topic=prompt.topic,
            used_at=prompt.used_at.isoformat(),
        )
    except Exception as e:
        reraise_known_ollama_error(e)
        logger.error(f"Failed to create weekly prompt: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate topic")


@router.get("/prompts/{prompt_id}", response_model=WritingPromptResponse)
async def get_prompt(prompt_id: int) -> WritingPromptResponse:
    """Get a single writing prompt by ID.

    Added to support the chat writing widget (Work Item B), which only has
    the prompt id (via ChatMessage.action_ref_id) and needs the prompt's
    topic/type to render WritingPromptCard, the same way the chat quiz
    widget already fetches its session via GET /api/quizzes/{session_id}.

    Args:
        prompt_id: The writing prompt ID

    Returns:
        WritingPromptResponse with prompt details

    Raises:
        HTTPException: If the prompt is not found
    """
    prompt = WritingService.get_prompt(prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Writing prompt not found")
    return WritingPromptResponse(
        id=prompt.id,
        prompt_type=prompt.prompt_type.value,
        topic=prompt.topic,
        used_at=prompt.used_at.isoformat(),
    )


@router.get("/prompts", response_model=PromptListResponse)
async def list_prompts(
    prompt_type: WritingPromptType | None = None,
    limit: int = 10,
) -> PromptListResponse:
    """List recent writing prompts.

    Args:
        prompt_type: Filter by prompt type (MINI or WEEKLY)
        limit: Maximum number of prompts to return

    Returns:
        PromptListResponse with prompts
    """
    try:
        if prompt_type:
            prompts = WritingService.get_recent_prompts(prompt_type, limit)
        else:
            # Get both types
            mini_prompts = WritingService.get_recent_prompts(
                WritingPromptType.MINI, limit
            )
            weekly_prompts = WritingService.get_recent_prompts(
                WritingPromptType.WEEKLY, limit
            )
            # Merge and sort by date
            prompts = sorted(
                mini_prompts + weekly_prompts,
                key=lambda p: p.used_at,
                reverse=True,
            )[:limit]

        return PromptListResponse(
            prompts=[
                WritingPromptResponse(
                    id=p.id,
                    prompt_type=p.prompt_type.value,
                    topic=p.topic,
                    used_at=p.used_at.isoformat(),
                )
                for p in prompts
            ]
        )
    except Exception as e:
        logger.error(f"Failed to list prompts: {e}")
        raise HTTPException(status_code=500, detail="Failed to list prompts")


@router.post("/submissions", response_model=WritingSubmitResponse)
async def submit_writing(request: SubmitWritingRequest) -> WritingSubmitResponse:
    """Submit and evaluate a writing.

    ARCHITECTURE Section 6.4:
    - POST /writing/submissions { prompt_id, text } - synchronous per ADR-08
    - Returns submission + evaluation

    Args:
        request: Writing submission request

    Returns:
        WritingSubmitResponse with submission and evaluation

    Raises:
        HTTPException: If submission or evaluation fails
    """
    try:
        submission, evaluation = await WritingService.submit_and_evaluate(
            prompt_id=request.prompt_id,
            text=request.text,
        )

        return WritingSubmitResponse(
            submission=WritingSubmissionResponse(
                id=submission.id,
                prompt_id=submission.prompt_id,
                submission_type=submission.submission_type.value,
                submitted_text=submission.submitted_text,
                word_count=submission.word_count,
                created_at=submission.created_at.isoformat(),
            ),
            evaluation=WritingEvaluationResponse(
                id=evaluation.id,
                submission_id=evaluation.submission_id,
                grammar_score=evaluation.grammar_score,
                naturalness_score=evaluation.naturalness_score,
                vocabulary_score=evaluation.vocabulary_score,
                coherence_score=evaluation.coherence_score,
                overall_score=evaluation.overall_score,
                feedback_json=evaluation.feedback_json,
                suggested_items_json=evaluation.suggested_items_json,
                evaluator_provider=evaluation.evaluator_provider,
                evaluator_model=evaluation.evaluator_model,
                prompt_version=evaluation.prompt_version,
                rubric_version=evaluation.rubric_version,
                created_at=evaluation.created_at.isoformat(),
            ),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        reraise_known_ollama_error(e)
        logger.error(f"Failed to submit writing: {e}")
        raise HTTPException(status_code=500, detail="Failed to evaluate writing")


@router.post("/submissions/{submission_id}/retry", response_model=WritingSubmitResponse)
async def retry_evaluation(submission_id: int) -> WritingSubmitResponse:
    """Retry evaluation for a failed submission.

    ARCHITECTURE Section 10.4 (state machine):
    - Called when evaluation failed previously
    - Re-runs evaluation against the already-stored text

    Args:
        submission_id: The submission ID to retry

    Returns:
        WritingSubmitResponse with submission and evaluation

    Raises:
        HTTPException: If submission not found or retry fails
    """
    try:
        submission, evaluation = await WritingService.retry_evaluation(submission_id)

        return WritingSubmitResponse(
            submission=WritingSubmissionResponse(
                id=submission.id,
                prompt_id=submission.prompt_id,
                submission_type=submission.submission_type.value,
                submitted_text=submission.submitted_text,
                word_count=submission.word_count,
                created_at=submission.created_at.isoformat(),
            ),
            evaluation=WritingEvaluationResponse(
                id=evaluation.id,
                submission_id=evaluation.submission_id,
                grammar_score=evaluation.grammar_score,
                naturalness_score=evaluation.naturalness_score,
                vocabulary_score=evaluation.vocabulary_score,
                coherence_score=evaluation.coherence_score,
                overall_score=evaluation.overall_score,
                feedback_json=evaluation.feedback_json,
                suggested_items_json=evaluation.suggested_items_json,
                evaluator_provider=evaluation.evaluator_provider,
                evaluator_model=evaluation.evaluator_model,
                prompt_version=evaluation.prompt_version,
                rubric_version=evaluation.rubric_version,
                created_at=evaluation.created_at.isoformat(),
            ),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        reraise_known_ollama_error(e)
        logger.error(f"Failed to retry evaluation: {e}")
        raise HTTPException(status_code=500, detail="Failed to retry evaluation")


@router.get("/submissions/{submission_id}", response_model=WritingSubmissionResponse)
async def get_submission(submission_id: int) -> WritingSubmissionResponse:
    """Get a writing submission by ID.

    Args:
        submission_id: The submission ID

    Returns:
        WritingSubmissionResponse with submission details

    Raises:
        HTTPException: If submission not found
    """
    submission = WritingService.get_submission(submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    return WritingSubmissionResponse(
        id=submission.id,
        prompt_id=submission.prompt_id,
        submission_type=submission.submission_type.value,
        submitted_text=submission.submitted_text,
        word_count=submission.word_count,
        created_at=submission.created_at.isoformat(),
    )


@router.get("/evaluations/{evaluation_id}", response_model=WritingEvaluationResponse)
async def get_evaluation(evaluation_id: int) -> WritingEvaluationResponse:
    """Get a writing evaluation by ID.

    Args:
        evaluation_id: The evaluation ID

    Returns:
        WritingEvaluationResponse with evaluation details

    Raises:
        HTTPException: If evaluation not found
    """
    evaluation = WritingService.get_evaluation(evaluation_id)
    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    return WritingEvaluationResponse(
        id=evaluation.id,
        submission_id=evaluation.submission_id,
        grammar_score=evaluation.grammar_score,
        naturalness_score=evaluation.naturalness_score,
        vocabulary_score=evaluation.vocabulary_score,
        coherence_score=evaluation.coherence_score,
        overall_score=evaluation.overall_score,
        feedback_json=evaluation.feedback_json,
        suggested_items_json=evaluation.suggested_items_json,
        evaluator_provider=evaluation.evaluator_provider,
        evaluator_model=evaluation.evaluator_model,
        prompt_version=evaluation.prompt_version,
        rubric_version=evaluation.rubric_version,
        created_at=evaluation.created_at.isoformat(),
    )
