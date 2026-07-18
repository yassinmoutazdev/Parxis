"""Writing Service for generating prompts and evaluating submissions.

Corresponds to ARCHITECTURE Section 6.4 (Weekly Writing Assessment sequence)
and Section 9.4/9.5 (Writing Evaluator prompts).
"""

import logging

from app.db.engine import Session
from app.db.models.approval import ApprovalQueue, ApprovalSourceType
from app.db.models.learning_item import LearningItem
from app.db.models.performance_error import PerformanceError, PerformanceErrorSource
from app.db.models.writing import (
    WritingEvaluation,
    WritingPrompt,
    WritingPromptType,
    WritingSubmission,
    WritingSubmissionType,
)
from app.llm import ollama_adapter
from app.llm.interface import TaskType
from app.llm.prompts.writing_eval import (
    get_mini_writing_eval_versions,
    get_weekly_writing_eval_versions,
)
from app.llm.provenance import stamp_provenance, to_dict
from app.llm.schemas import (
    MiniWritingEvalOutput,
    ParsedItem,
    WeeklyWritingEvalOutput,
)
from app.llm.validation import validate_output
from app.retrieval.service import RetrievalService

logger = logging.getLogger(__name__)


class WritingService:
    """Service for writing prompt generation and evaluation.

    Handles the writing lifecycle: generating prompts (mini/weekly),
    storing submissions, evaluating submissions, and managing results.
    """

    # Number of recent prompts to fetch for fuzzy-match retry
    RECENT_PROMPTS_LIMIT = 12

    @classmethod
    def generate_mini_prompt(cls) -> WritingPrompt:
        """Generate a mini writing prompt.

        For mini tasks, we use a simple prompt since there's no retry logic
        needed (no fuzzy-match against previous topics).

        Returns:
            WritingPrompt with prompt text
        """

        topic_text = "Write 2-3 sentences about your day or a topic of your choice"

        with Session() as session:
            prompt = WritingPrompt(
                prompt_type=WritingPromptType.MINI,
                topic=topic_text,
            )
            session.add(prompt)
            session.commit()
            session.refresh(prompt)
            return prompt

    @classmethod
    async def generate_weekly_prompt(cls) -> WritingPrompt:
        """Generate a weekly writing prompt with fuzzy-match retry.

        ARCHITECTURE Section 9.7 (Topic Generation):
        - Fetch last 12 WEEKLY prompts via RetrievalService
        - Call Generator.generate(task="weekly_topic", ...)
        - Apply fuzzy-match retry rule: on match, one retry with offending topic excluded
        - Persist WritingPrompt

        Returns:
            WritingPrompt with topic and prompt_text
        """
        from app.llm.schemas import TopicOutput

        with Session() as session:
            # Fetch recent weekly prompts for fuzzy-match
            recent_prompts = (
                session.query(WritingPrompt)
                .filter(WritingPrompt.prompt_type == WritingPromptType.WEEKLY)
                .order_by(WritingPrompt.used_at.desc())
                .limit(cls.RECENT_PROMPTS_LIMIT)
                .all()
            )

            recent_topics = [p.topic for p in recent_prompts]

            # Build context with recent topics to avoid
            context = {
                "avoid": recent_topics,
                "recent_topics": recent_topics,
            }

            # Try to generate with retry on fuzzy match
            max_attempts = 2
            prompt_obj: WritingPrompt | None = None

            for attempt in range(max_attempts):
                try:
                    result = await ollama_adapter.ollama_adapter.generate(
                        task=TaskType.WEEKLY_TOPIC,
                        context=context,
                        output_schema=TopicOutput,
                    )

                    # Validate against recent topics (fuzzy match)
                    warnings: list[str] = []
                    topic_lower = result.topic.lower()

                    for recent in recent_topics:
                        if recent.lower() in topic_lower or topic_lower in recent.lower():
                            warnings.append(
                                f"topic '{result.topic}' matches recent topic '{recent}'"
                            )
                            # Retry with this topic excluded from avoid list
                            if attempt == 0:
                                context["avoid"] = recent_topics + [result.topic]
                            break

                    if not warnings:
                        # Valid topic - create the prompt
                        prompt_obj = WritingPrompt(
                            prompt_type=WritingPromptType.WEEKLY,
                            topic=result.topic,
                        )
                        session.add(prompt_obj)
                        session.commit()
                        session.refresh(prompt_obj)
                        return prompt_obj

                except Exception as e:
                    logger.warning(f"Topic generation attempt {attempt + 1} failed: {e}")
                    if attempt == max_attempts - 1:
                        raise

            # Fallback: if all retries fail, create a generic prompt
            logger.warning("Weekly topic generation failed, using fallback topic")
            prompt_obj = WritingPrompt(
                prompt_type=WritingPromptType.WEEKLY,
                topic="Describe a memorable experience and what you learned from it",
            )
            session.add(prompt_obj)
            session.commit()
            session.refresh(prompt_obj)
            return prompt_obj

    @classmethod
    def get_recent_prompts(
        cls,
        prompt_type: WritingPromptType,
        limit: int = 10,
    ) -> list[WritingPrompt]:
        """Get recent writing prompts.

        Args:
            prompt_type: Type of prompts to fetch
            limit: Maximum number of prompts to return

        Returns:
            List of recent WritingPrompts
        """
        with Session() as session:
            return (
                session.query(WritingPrompt)
                .filter(WritingPrompt.prompt_type == prompt_type)
                .order_by(WritingPrompt.used_at.desc())
                .limit(limit)
                .all()
            )

    @classmethod
    async def submit_and_evaluate(
        cls,
        prompt_id: int,
        text: str,
    ) -> tuple[WritingSubmission, WritingEvaluation]:
        """Submit and evaluate a writing submission.

        ARCHITECTURE Section 6.4 (sequence diagram):
        1. INSERT WritingSubmission
        2. Get writing context via RetrievalService
        3. Call Evaluator.evaluate(task=...)
        4. On failure: WritingEvaluation.status = EVALUATION_FAILED; return error
        5. INSERT WritingEvaluation with scores + provenance
        6. For mini task: INSERT PerformanceError rows (ADR-05 exception)
        7. For suggested_items: INSERT ApprovalQueue rows (approval-gated)

        Args:
            prompt_id: The writing prompt ID
            text: The learner's submission text

        Returns:
            Tuple of (WritingSubmission, WritingEvaluation)
        """
        with Session() as session:
            # Load the prompt to determine type
            prompt = session.get(WritingPrompt, prompt_id)
            if not prompt:
                raise ValueError(f"WritingPrompt {prompt_id} not found")

            # Determine submission type
            submission_type = (
                WritingSubmissionType.MINI
                if prompt.prompt_type == WritingPromptType.MINI
                else WritingSubmissionType.WEEKLY
            )

            # Calculate word count
            word_count = len(text.split())

            # Create submission
            submission = WritingSubmission(
                prompt_id=prompt_id,
                submission_type=submission_type,
                submitted_text=text,
                word_count=word_count,
            )
            session.add(submission)
            session.flush()

            # Get evaluation context
            ctx = cls._build_evaluation_context(text)

            # Determine task type and evaluate
            if submission_type == WritingSubmissionType.MINI:
                evaluation = await cls._evaluate_mini(
                    session=session,
                    submission=submission,
                    text=text,
                    context=ctx,
                )
            else:
                evaluation = await cls._evaluate_weekly(
                    session=session,
                    submission=submission,
                    text=text,
                    context=ctx,
                )

            session.commit()
            session.refresh(submission)
            session.refresh(evaluation)

            return submission, evaluation

    @classmethod
    def _build_evaluation_context(cls, text: str) -> dict:
        """Build context for writing evaluation.

        Args:
            text: The submission text

        Returns:
            Dictionary with context for evaluation
        """
        # Get writing context from RetrievalService
        ctx = RetrievalService.writing_context(text)

        # Format known_relevant_items for the prompt
        known_items = ctx.get("known_relevant_items", [])
        known_relevant_items_formatted = []
        for item in known_items:
            if isinstance(item, LearningItem):
                known_relevant_items_formatted.append({
                    "text": item.text,
                    "definition": item.definition or "",
                })

        # Format weak categories
        weak_categories = ctx.get("weak_categories", [])

        return {
            "submission_text": text,
            "weak_categories": ", ".join(weak_categories) if weak_categories else "general writing",
            "known_relevant_items": "\n".join(
                f"- {item['text']}: {item['definition']}"
                for item in known_relevant_items_formatted
            ) if known_relevant_items_formatted else "No relevant items found",
            "content": text,  # For prompt template formatting
        }

    @classmethod
    async def _evaluate_mini(
        cls,
        session: Session,
        submission: WritingSubmission,
        text: str,
        context: dict,
    ) -> WritingEvaluation:
        """Evaluate a mini writing submission.

        Args:
            session: Database session
            submission: The writing submission
            text: The submission text
            context: Evaluation context

        Returns:
            WritingEvaluation with results
        """
        # Get version info
        prompt_version, rubric_version = get_mini_writing_eval_versions()

        try:
            # Call evaluator
            result = await ollama_adapter.ollama_adapter.evaluate(
                task=TaskType.MINI_WRITING_EVAL,
                content=text,
                context=context,
                output_schema=MiniWritingEvalOutput,
            )

            # Validate output
            result = validate_output(TaskType.MINI_WRITING_EVAL, result)

        except Exception as e:
            logger.error(f"Mini writing evaluation failed: {e}")
            # Create failed evaluation (no scores for mini)
            evaluation = WritingEvaluation(
                submission_id=submission.id,
                feedback_json={"error": str(e)},
            )
            session.add(evaluation)
            session.flush()
            raise

        # Create evaluation with scores (mini uses overall_score only if present)
        overall_score = None
        if result.corrections:
            # Calculate a simple score based on corrections
            # Fewer corrections = higher score
            overall_score = max(0.0, 1.0 - (len(result.corrections) * 0.2))

        evaluation = WritingEvaluation(
            submission_id=submission.id,
            overall_score=overall_score,
            feedback_json={
                "corrections": [
                    {
                        "wrong": c.wrong,
                        "correct": c.correct,
                        "explanation": c.explanation,
                    }
                    for c in result.corrections
                ],
                "naturalness_notes": result.naturalness_notes,
            },
            suggested_items_json=[
                cls._parsed_item_to_dict(item)
                for item in result.suggested_items
            ] if result.suggested_items else None,
            # Provenance (ADR-13)
            **cls._get_provenance(prompt_version, rubric_version),
        )
        session.add(evaluation)
        session.flush()

        # Create PerformanceError rows for each correction (ADR-05 exception)
        for correction in result.corrections:
            error = PerformanceError(
                learning_item_id=None,
                wrong_form=correction.wrong,
                correct_form=correction.correct,
                explanation=correction.explanation,
                source_type=PerformanceErrorSource.WRITING_MINI,
                source_id=submission.id,
            )
            session.add(error)

        # Route suggested_items to ApprovalQueue (approval-gated)
        for item in result.suggested_items:
            cls._create_approval_queue_item(
                session=session,
                item=item,
                source_id=submission.id,
            )

        return evaluation

    @classmethod
    async def _evaluate_weekly(
        cls,
        session: Session,
        submission: WritingSubmission,
        text: str,
        context: dict,
    ) -> WritingEvaluation:
        """Evaluate a weekly writing submission.

        Args:
            session: Database session
            submission: The writing submission
            text: The submission text
            context: Evaluation context

        Returns:
            WritingEvaluation with 5 dimension scores
        """
        # Get version info
        prompt_version, rubric_version = get_weekly_writing_eval_versions()

        try:
            # Call evaluator
            result = await ollama_adapter.ollama_adapter.evaluate(
                task=TaskType.WEEKLY_WRITING_EVAL,
                content=text,
                context=context,
                output_schema=WeeklyWritingEvalOutput,
            )

            # Validate output
            result, warnings = validate_output(TaskType.WEEKLY_WRITING_EVAL, result)

            if warnings:
                logger.warning(f"Weekly writing evaluation warnings: {warnings}")

        except Exception as e:
            logger.error(f"Weekly writing evaluation failed: {e}")
            # Create failed evaluation
            evaluation = WritingEvaluation(
                submission_id=submission.id,
                feedback_json={"error": str(e)},
            )
            session.add(evaluation)
            session.flush()
            raise

        # Create evaluation with 5 dimension scores
        evaluation = WritingEvaluation(
            submission_id=submission.id,
            grammar_score=result.grammar.score,
            naturalness_score=result.naturalness.score,
            vocabulary_score=result.vocabulary.score,
            coherence_score=result.coherence.score,
            overall_score=result.overall.score,
            feedback_json={
                "grammar": result.grammar.feedback,
                "naturalness": result.naturalness.feedback,
                "vocabulary": result.vocabulary.feedback,
                "coherence": result.coherence.feedback,
                "overall": result.overall.feedback,
            },
            suggested_items_json=[
                cls._parsed_item_to_dict(item)
                for item in result.suggested_items
            ] if result.suggested_items else None,
            # Provenance (ADR-13)
            **cls._get_provenance(prompt_version, rubric_version),
        )
        session.add(evaluation)
        session.flush()

        # Route suggested_items to ApprovalQueue (approval-gated)
        for item in result.suggested_items:
            cls._create_approval_queue_item(
                session=session,
                item=item,
                source_id=submission.id,
            )

        return evaluation

    @classmethod
    def _get_provenance(
        cls,
        prompt_version: str,
        rubric_version: str | None,
    ) -> dict:
        """Get provenance dictionary for evaluation.

        Args:
            prompt_version: Prompt version string
            rubric_version: Rubric version string

        Returns:
            Dictionary with provenance fields
        """
        provenance = stamp_provenance(prompt_version, rubric_version)
        return to_dict(provenance)

    @classmethod
    def _parsed_item_to_dict(cls, item: ParsedItem) -> dict:
        """Convert ParsedItem to dictionary for storage.

        Args:
            item: ParsedItem to convert

        Returns:
            Dictionary representation
        """
        return {
            "item_type": item.item_type,
            "text": item.text,
            "definition": item.definition,
            "example_sentence": item.example_sentence,
            "source_excerpt": item.source_excerpt,
            "wrong_form": item.wrong_form,
            "correct_form": item.correct_form,
        }

    @classmethod
    def _create_approval_queue_item(
        cls,
        session: Session,
        item: ParsedItem,
        source_id: int,
    ) -> None:
        """Create an ApprovalQueue item from a suggested item.

        This is the approval-gated path for new knowledge extracted from
        writing feedback (ADR-05).

        Args:
            session: Database session
            item: Suggested ParsedItem
            source_id: Source submission ID
        """
        queue_item = ApprovalQueue(
            source_type=ApprovalSourceType.WRITING_FEEDBACK,
            source_id=source_id,
            item_type=item.item_type,
            extracted_text=item.text,
            explanation=item.definition,
            example_sentence=item.example_sentence,
            source_context=item.source_excerpt,
        )
        session.add(queue_item)

    @classmethod
    async def retry_evaluation(
        cls,
        submission_id: int,
    ) -> tuple[WritingSubmission, WritingEvaluation]:
        """Retry evaluation for a failed submission.

        ARCHITECTURE Section 10.4 (state machine):
        - Called when WritingEvaluation.status = EVALUATION_FAILED
        - Re-runs evaluation against the already-stored text

        Args:
            submission_id: The submission ID to retry

        Returns:
            Tuple of (WritingSubmission, WritingEvaluation)
        """
        with Session() as session:
            # Load submission
            submission = session.get(WritingSubmission, submission_id)
            if not submission:
                raise ValueError(f"WritingSubmission {submission_id} not found")

            # Get the prompt
            prompt = session.get(WritingPrompt, submission.prompt_id)
            if not prompt:
                raise ValueError(f"WritingPrompt {submission.prompt_id} not found")

            # Build evaluation context
            context = cls._build_evaluation_context(submission.submitted_text)

            # Re-evaluate based on submission type
            if submission.submission_type == WritingSubmissionType.MINI:
                evaluation = await cls._evaluate_mini(
                    session=session,
                    submission=submission,
                    text=submission.submitted_text,
                    context=context,
                )
            else:
                evaluation = await cls._evaluate_weekly(
                    session=session,
                    submission=submission,
                    text=submission.submitted_text,
                    context=context,
                )

            session.commit()
            session.refresh(submission)
            session.refresh(evaluation)

            return submission, evaluation

    @classmethod
    def get_submission(cls, submission_id: int) -> WritingSubmission | None:
        """Get a writing submission by ID.

        Args:
            submission_id: The submission ID

        Returns:
            WritingSubmission if found
        """
        with Session() as session:
            return session.get(WritingSubmission, submission_id)

    @classmethod
    def get_evaluation(cls, evaluation_id: int) -> WritingEvaluation | None:
        """Get a writing evaluation by ID.

        Args:
            evaluation_id: The evaluation ID

        Returns:
            WritingEvaluation if found
        """
        with Session() as session:
            return session.get(WritingEvaluation, evaluation_id)

    @classmethod
    def get_prompt(cls, prompt_id: int) -> WritingPrompt | None:
        """Get a writing prompt by ID.

        Args:
            prompt_id: The prompt ID

        Returns:
            WritingPrompt if found
        """
        with Session() as session:
            return session.get(WritingPrompt, prompt_id)
