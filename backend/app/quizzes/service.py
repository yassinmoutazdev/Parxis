"""Quiz Service for generating and grading quizzes.

Corresponds to ARCHITECTURE Section 6.3 (Quiz Generation & Grading).
"""

import logging
import random
from datetime import date, datetime

logger = logging.getLogger(__name__)

from app.db.engine import Session
from app.db.models.learning_item import LearningItem
from app.db.models.performance_error import PerformanceError, PerformanceErrorSource
from app.db.models.quiz import GradedBy, QuizMode, QuizQuestion, QuizScope, QuizSession
from app.llm import ollama_adapter
from app.llm.interface import TaskType
from app.llm.schemas import QuizQuestionOutput
from app.llm.validation import validate_output
from app.retrieval.service import RetrievalService
from app.scheduler.mastery import SchedulerSettings, update_mastery


class QuizService:
    """Service for quiz generation and grading.

    Handles the full quiz lifecycle: start session, generate questions,
    grade answers, and update mastery.
    """

    @classmethod
    async def start_session(
        cls,
        size: int,
        scope: QuizScope = QuizScope.AD_HOC,
        week_id: int | None = None,
        since: date | None = None,
    ) -> tuple[QuizSession, list[QuizQuestion]]:
        """Start a new quiz session.

        ARCHITECTURE Section 6.3 (sequence diagram, session-start portion):
        1. Call RetrievalService.select_eligible_items() to get learning items
        2. Create QuizSession with status=IN_PROGRESS
        3. For each selected item:
           - Get prompt context via RetrievalService.item_context()
           - Call Generator.generate(task="quiz_multiple_choice", ...)
           - Persist QuizQuestion row
        4. Return QuizSession + QuizQuestion[] (prompts only, no answers)

        Args:
            size: Number of questions to generate
            scope: Quiz scope (AD_HOC or WEEKLY_REVIEW)
            week_id: Optional week ID for weekly quizzes
            since: Optional date to bias item selection toward items
                   created/reviewed since this date (used for weekly quiz)

        Returns:
            Tuple of (QuizSession, list of QuizQuestion)
        """
        # Select eligible items
        items = RetrievalService.select_eligible_items(size=size, since=since)
        if not items:
            raise ValueError("No eligible items found for quiz")

        # Get more items for backfill if needed
        backfill_items = RetrievalService.select_eligible_items(size=size * 2, since=since)
        # Filter out items already selected
        selected_ids = {item.id for item in items}
        backfill_pool = [item for item in backfill_items if item.id not in selected_ids]

        # Create session (always MULTIPLE_CHOICE mode)
        with Session() as session:
            quiz_session = QuizSession(
                quiz_scope=scope,
                quiz_mode=QuizMode.MULTIPLE_CHOICE,
                started_at=datetime.utcnow(),
                week_id=week_id,
            )
            session.add(quiz_session)
            session.flush()  # Get the session ID

            # Generate questions for each item with retry/backfill logic
            questions: list[QuizQuestion] = []
            backfill_index = 0

            for item in items:
                # First attempt
                question = await cls._generate_question(
                    session=session,
                    item=item,
                    quiz_session_id=quiz_session.id,
                    retry_count=0,
                )

                if question:
                    questions.append(question)
                else:
                    # Retry with backfill item
                    if backfill_index < len(backfill_pool):
                        backfill_item = backfill_pool[backfill_index]
                        backfill_index += 1

                        question = await cls._generate_question(
                            session=session,
                            item=backfill_item,
                            quiz_session_id=quiz_session.id,
                            retry_count=1,
                        )

                        if question:
                            questions.append(question)
                            # Add this backfill item to selected IDs so we don't reuse
                            selected_ids.add(backfill_item.id)

            session.commit()
            session.refresh(quiz_session)
            for q in questions:
                session.refresh(q)

            return quiz_session, questions

    @classmethod
    async def _generate_question(
        cls,
        session: Session,
        item: LearningItem,
        quiz_session_id: int,
        retry_count: int = 0,
    ) -> QuizQuestion | None:
        """Generate a single quiz question for a learning item.

        Args:
            session: Database session
            item: LearningItem to generate question for
            quiz_session_id: The quiz session ID
            retry_count: Current retry attempt (for validation failure retry)

        Returns:
            QuizQuestion if successful, None if validation failed after retries
        """
        # Always use MULTIPLE_CHOICE mode
        question_mode = QuizMode.MULTIPLE_CHOICE

        # Get the task name for the generator
        task = TaskType.QUIZ_MULTIPLE_CHOICE

        # Get prompt context from the learning item
        prompt_context = RetrievalService.item_context(item)
        # Format context for prompt template
        formatted_context = {
            "item_text": prompt_context.get("text", ""),
            "item_definition": prompt_context.get("definition", ""),
            "item_example": prompt_context.get("example_sentence", ""),
        }

        try:
            # Generate the question
            result = await ollama_adapter.ollama_adapter.generate(
                task=task,
                context=formatted_context,
                output_schema=QuizQuestionOutput,
            )

            # Validate the output (returns tuple, unpack it)
            result, warnings = validate_output(task, result)

            # If validation failed (result is None), skip this item
            if result is None:
                logger.warning(f"Question validation failed for item {item.id}: {warnings}")
                return None

            # Build options list for MULTIPLE_CHOICE (shuffled correct + distractors)
            options_json: list[str] | None = None
            if result.distractors:
                options_json = [result.correct_answer] + result.distractors
                random.shuffle(options_json)

            # Create the QuizQuestion row
            question = QuizQuestion(
                quiz_session_id=quiz_session_id,
                learning_item_id=item.id,
                question_type=question_mode,
                prompt=result.prompt_text,
                correct_answer=result.correct_answer,
                options_json=options_json,
            )
            session.add(question)
            session.flush()

            return question

        except Exception:
            # Handle validation failure with retry
            if retry_count == 0:
                # First failure: retry with next eligible item
                return None
            else:
                # Second failure: skip this item
                return None

    @classmethod
    async def grade_session(
        cls,
        session_id: int,
        answers: dict[int, str],
    ) -> QuizSession:
        """Grade a quiz session.

        ARCHITECTURE Section 6.3 (sequence diagram, grading portion):
        1. For each answer:
           - Deterministic grading (all questions are MULTIPLE_CHOICE)
           - Update QuizQuestion with user_answer, is_correct/score, feedback, graded_by
           - If incorrect (score < CORRECT_THRESHOLD): INSERT PerformanceError row
           - Update mastery via SchedulerModule.update_mastery()
        2. Mark QuizSession.completed_at
        3. Return session summary

        Args:
            session_id: The quiz session ID
            answers: Dict mapping question_id to user's answer

        Returns:
            The completed QuizSession
        """
        from app.quizzes.grading import grade_deterministic

        with Session() as session:
            # Load the session
            quiz_session = session.get(QuizSession, session_id)
            if not quiz_session:
                raise ValueError(f"Quiz session {session_id} not found")

            # Load all questions for this session
            questions = (
                session.query(QuizQuestion)
                .filter(QuizQuestion.quiz_session_id == session_id)
                .all()
            )

            settings = SchedulerSettings.get()

            # Grade each answer (all MULTIPLE_CHOICE - deterministic)
            for question in questions:
                user_answer = answers.get(question.id)
                if user_answer is None:
                    continue

                question.user_answer = user_answer

                # Deterministic grading for MULTIPLE_CHOICE
                is_correct, score, feedback = grade_deterministic(
                    question_type=question.question_type,
                    correct_answer=question.correct_answer,
                    user_answer=user_answer,
                )
                question.graded_by = GradedBy.DETERMINISTIC
                question.feedback = feedback

                question.is_correct = is_correct
                question.score = score

                # If incorrect or low score, create PerformanceError row
                if not is_correct or (score is not None and score < settings.correct_threshold):
                    cls._create_performance_error(
                        session=session,
                        question=question,
                        user_answer=user_answer,
                    )

                # Update mastery
                if question.learning_item_id:
                    item = session.get(LearningItem, question.learning_item_id)
                    if item:
                        update_mastery(item, score or 0.0)
                        session.add(item)

            # Mark session as completed
            quiz_session.completed_at = datetime.utcnow()

            session.commit()
            session.refresh(quiz_session)
            return quiz_session

    @classmethod
    def _create_performance_error(
        cls,
        session: Session,
        question: QuizQuestion,
        user_answer: str,
    ) -> None:
        """Create a PerformanceError row for an incorrect answer.

        This is the ADR-05 exception: PerformanceError rows are written
        directly by QuizService with no approval step.

        Args:
            session: Database session
            question: The QuizQuestion that was answered incorrectly
            user_answer: The user's wrong answer
        """
        error = PerformanceError(
            learning_item_id=question.learning_item_id,
            wrong_form=user_answer,
            correct_form=question.correct_answer or "",
            explanation=question.feedback or "",
            source_type=PerformanceErrorSource.QUIZ,
            source_id=question.id,
        )
        session.add(error)

    @classmethod
    def get_session(cls, session_id: int) -> QuizSession | None:
        """Get a quiz session by ID.

        Args:
            session_id: The quiz session ID

        Returns:
            The QuizSession if found
        """
        with Session() as session:
            return session.get(QuizSession, session_id)

    @classmethod
    def get_session_with_questions(
        cls, session_id: int
    ) -> tuple[QuizSession, list[QuizQuestion]]:
        """Get a quiz session with all its questions.

        Args:
            session_id: The quiz session ID

        Returns:
            Tuple of (QuizSession, list of QuizQuestion)
        """
        with Session() as session:
            quiz_session = session.get(QuizSession, session_id)
            if not quiz_session:
                raise ValueError(f"Quiz session {session_id} not found")

            questions = (
                session.query(QuizQuestion)
                .filter(QuizQuestion.quiz_session_id == session_id)
                .all()
            )

            return quiz_session, questions
