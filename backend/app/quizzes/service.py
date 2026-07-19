"""Quiz Service for generating and grading quizzes.

Corresponds to ARCHITECTURE Section 6.3 (Quiz Generation & Grading).
"""

import random
from datetime import datetime

from app.db.engine import Session
from app.db.models.learning_item import LearningItem
from app.db.models.performance_error import PerformanceError, PerformanceErrorSource
from app.db.models.quiz import GradedBy, QuizMode, QuizQuestion, QuizScope, QuizSession
from app.llm import ollama_adapter
from app.llm.interface import TaskType
from app.llm.provenance import stamp_provenance, to_dict
from app.llm.schemas import GradedAnswerOutput, QuizQuestionOutput
from app.llm.validation import validate_output
from app.retrieval.service import RetrievalService
from app.scheduler.mastery import SchedulerSettings, update_mastery


class QuizService:
    """Service for quiz generation and grading.

    Handles the full quiz lifecycle: start session, generate questions,
    grade answers, and update mastery.
    """

    # Quiz modes that require deterministic grading
    DETERMINISTIC_GRADING_MODES = frozenset(
        {
            QuizMode.RECALL,
            QuizMode.FILL_BLANK,
            QuizMode.MULTIPLE_CHOICE,
        }
    )

    # Quiz modes that use LLM grading (free-text)
    LLM_GRADING_MODES = frozenset(
        {
            QuizMode.ERROR_CORRECTION,
            QuizMode.REWRITE_NATURALLY,
            QuizMode.CONVERSATION,
            QuizMode.MINI_ESSAY,
        }
    )

    @classmethod
    async def start_session(
        cls,
        mode: QuizMode,
        size: int,
        scope: QuizScope = QuizScope.AD_HOC,
        week_id: int | None = None,
    ) -> tuple[QuizSession, list[QuizQuestion]]:
        """Start a new quiz session.

        ARCHITECTURE Section 6.3 (sequence diagram, session-start portion):
        1. Call RetrievalService.select_eligible_items() to get learning items
        2. Create QuizSession with status=IN_PROGRESS
        3. For each selected item:
           - Get prompt context via RetrievalService.item_context()
           - Call Generator.generate(task=f"quiz_{mode}", ...)
           - Persist QuizQuestion row
        4. Return QuizSession + QuizQuestion[] (prompts only, no answers)

        Args:
            mode: Quiz mode (RECALL, FILL_BLANK, etc. or RANDOM)
            size: Number of questions to generate
            scope: Quiz scope (AD_HOC or WEEKLY_REVIEW)
            week_id: Optional week ID for weekly quizzes

        Returns:
            Tuple of (QuizSession, list of QuizQuestion)
        """
        # Select eligible items
        items = RetrievalService.select_eligible_items(size=size)
        if not items:
            raise ValueError("No eligible items found for quiz")

        # Get more items for backfill if needed
        backfill_items = RetrievalService.select_eligible_items(size=size * 2)
        # Filter out items already selected
        selected_ids = {item.id for item in items}
        backfill_pool = [item for item in backfill_items if item.id not in selected_ids]

        # Create session
        with Session() as session:
            quiz_session = QuizSession(
                quiz_scope=scope,
                quiz_mode=mode,
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
                    session_mode=mode,
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
                            session_mode=mode,
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
        session_mode: QuizMode,
        quiz_session_id: int,
        retry_count: int = 0,
    ) -> QuizQuestion | None:
        """Generate a single quiz question for a learning item.

        Args:
            session: Database session
            item: LearningItem to generate question for
            session_mode: The session's quiz mode (or RANDOM)
            quiz_session_id: The quiz session ID
            retry_count: Current retry attempt (for validation failure retry)

        Returns:
            QuizQuestion if successful, None if validation failed after retries
        """
        # Determine the mode for this question
        if session_mode == QuizMode.RANDOM:
            # Random mode: pick one of the 7 concrete modes
            question_mode = cls._select_random_mode()
        else:
            question_mode = session_mode

        # Get the task name for the generator
        task = cls._mode_to_task(question_mode)

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

            # Create the QuizQuestion row
            question = QuizQuestion(
                quiz_session_id=quiz_session_id,
                learning_item_id=item.id,
                question_type=question_mode,
                prompt=result.prompt_text,
                correct_answer=result.correct_answer,
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
    def _select_random_mode(cls) -> QuizMode:
        """Select a random concrete quiz mode.

        Excludes RANDOM mode itself - returns one of the 7 concrete modes.

        Returns:
            A random concrete QuizMode
        """
        concrete_modes = [
            QuizMode.RECALL,
            QuizMode.FILL_BLANK,
            QuizMode.MULTIPLE_CHOICE,
            QuizMode.ERROR_CORRECTION,
            QuizMode.REWRITE_NATURALLY,
            QuizMode.CONVERSATION,
            QuizMode.MINI_ESSAY,
        ]
        return random.choice(concrete_modes)

    @classmethod
    def _mode_to_task(cls, mode: QuizMode) -> str:
        """Convert QuizMode to generator task name.

        Args:
            mode: QuizMode to convert

        Returns:
            Task name string (e.g., 'quiz_recall')
        """
        mode_to_task = {
            QuizMode.RECALL: TaskType.QUIZ_RECALL,
            QuizMode.FILL_BLANK: TaskType.QUIZ_FILL_BLANK,
            QuizMode.MULTIPLE_CHOICE: TaskType.QUIZ_MULTIPLE_CHOICE,
            QuizMode.ERROR_CORRECTION: TaskType.QUIZ_ERROR_CORRECTION,
            QuizMode.REWRITE_NATURALLY: TaskType.QUIZ_REWRITE_NATURALLY,
            QuizMode.CONVERSATION: TaskType.QUIZ_CONVERSATION,
            QuizMode.MINI_ESSAY: TaskType.QUIZ_MINI_ESSAY,
            QuizMode.RANDOM: TaskType.QUIZ_RANDOM,
        }
        return mode_to_task.get(mode, TaskType.QUIZ_RECALL)

    @classmethod
    async def grade_session(
        cls,
        session_id: int,
        answers: dict[int, str],
    ) -> QuizSession:
        """Grade a quiz session.

        ARCHITECTURE Section 6.3 (sequence diagram, grading portion):
        1. For each answer:
           - If deterministic type: grade_deterministic()
           - Else: LLM grading via Evaluator.evaluate(task="grade_quiz_answer")
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

            # Grade each answer
            for question in questions:
                user_answer = answers.get(question.id)
                if user_answer is None:
                    continue

                question.user_answer = user_answer

                # Determine grading method based on question type
                provenance = None
                if question.question_type in cls.DETERMINISTIC_GRADING_MODES:
                    # Deterministic grading
                    is_correct, score, feedback = grade_deterministic(
                        question_type=question.question_type,
                        correct_answer=question.correct_answer,
                        user_answer=user_answer,
                        distractors=None,  # TODO: add distractors to model
                    )
                    question.graded_by = GradedBy.DETERMINISTIC
                else:
                    # LLM grading with provenance stamping (ADR-13)
                    is_correct, score, feedback, provenance = await cls._grade_with_llm(
                        question=question,
                        user_answer=user_answer,
                    )
                    question.graded_by = GradedBy.LLM
                    if provenance:
                        question.evaluator_provider = provenance.get("evaluator_provider")
                        question.evaluator_model = provenance.get("evaluator_model")
                        question.prompt_version = provenance.get("prompt_version")
                        question.rubric_version = provenance.get("rubric_version")

                question.is_correct = is_correct
                question.score = score
                question.feedback = feedback

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
    async def _grade_with_llm(
        cls,
        question: QuizQuestion,
        user_answer: str,
    ) -> tuple[bool, float, str, dict[str, str | None] | None]:
        """Grade a quiz answer using LLM evaluation.

        Args:
            question: The QuizQuestion being graded
            user_answer: The user's answer

        Returns:
            Tuple of (is_correct, score, feedback, provenance_dict)
        """

        # Build context for grading
        context = {
            "question_prompt": question.prompt,
            "expected_answer": question.correct_answer or "",
            "learner_answer": user_answer,
        }

        # Call the evaluator
        result = await ollama_adapter.ollama_adapter.evaluate(
            task=TaskType.GRADE_QUIZ_ANSWER,
            content=user_answer,
            context=context,
            output_schema=GradedAnswerOutput,
        )

        # Validate and clamp the score
        validate_output(result, GradedAnswerOutput)
        score = max(0.0, min(1.0, result.score))

        # Determine if correct based on threshold
        settings = SchedulerSettings.get()
        is_correct = score >= settings.correct_threshold

        # Create provenance stamp (ADR-13)
        provenance = stamp_provenance(prompt_version="1.0.0")  # TODO: use actual version from prompts
        provenance_dict = to_dict(provenance)

        return is_correct, score, result.feedback, provenance_dict

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
