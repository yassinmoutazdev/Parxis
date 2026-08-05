"""LLM Generator and Evaluator Protocol interfaces.

This module defines the abstract contracts for generating and evaluating content,
allowing different LLM backends to be plugged in.
"""

from typing import Any, Protocol

from pydantic import BaseModel


class Generator(Protocol):
    """Protocol for generating content from LLM.

    The Generator is responsible for creating new content (like quiz questions,
    parsed note items, or narrative reports) based on input context.
    """

    async def generate(
        self,
        task: str,
        context: dict[str, Any],
        output_schema: type[BaseModel],
    ) -> BaseModel:
        """Generate content based on a task and context.

        Args:
            task: The task identifier (e.g., 'parse_note', 'quiz_recall', 'weekly_narrative')
            context: Context data for the generation task
            output_schema: Pydantic model class defining the expected output structure

        Returns:
            An instance of the output_schema with generated content

        Raises:
            Exception: If generation fails after retries
        """
        ...


class Evaluator(Protocol):
    """Protocol for evaluating content with LLM.

    The Evaluator is responsible for grading or evaluating content (like quiz answers
    or writing submissions) based on provided context.
    """

    async def evaluate(
        self,
        task: str,
        content: str,
        context: dict[str, Any],
        output_schema: type[BaseModel],
    ) -> BaseModel:
        """Evaluate content based on a task and context.

        Args:
            task: The task identifier (e.g., 'grade_quiz_answer', 'mini_writing_eval')
            content: The content to evaluate
            context: Context data for the evaluation task
            output_schema: Pydantic model class defining the expected output structure

        Returns:
            An instance of the output_schema with evaluation results

        Raises:
            Exception: If evaluation fails after retries
        """
        ...


class TaskType:
    """Task type constants for LLM operations."""

    # Parsing tasks
    PARSE_NOTE = "parse_note"

    # Quiz generation tasks
    QUIZ_RECALL = "quiz_recall"
    QUIZ_FILL_BLANK = "quiz_fill_blank"
    QUIZ_MULTIPLE_CHOICE = "quiz_multiple_choice"
    QUIZ_ERROR_CORRECTION = "quiz_error_correction"
    QUIZ_REWRITE_NATURALLY = "quiz_rewrite_naturally"
    QUIZ_RANDOM = "quiz_random"

    # Quiz grading tasks
    GRADE_QUIZ_ANSWER = "grade_quiz_answer"

    # Writing evaluation tasks
    MINI_WRITING_EVAL = "mini_writing_eval"
    WEEKLY_WRITING_EVAL = "weekly_writing_eval"

    # Report generation tasks
    WEEKLY_TOPIC = "weekly_topic"
    WEEKLY_NARRATIVE = "weekly_narrative"

    # Chat coach tasks
    COACH_CHAT = "coach_chat"
    COACH_CHAT_AFTER_QUIZ = "coach_chat_after_quiz"
    COACH_CHAT_AFTER_WRITING = "coach_chat_after_writing"
    COACH_THREAD_TITLE = "coach_thread_title"

    # All generation tasks (for reference)
    GENERATION_TASKS = frozenset(
        {
            PARSE_NOTE,
            QUIZ_RECALL,
            QUIZ_FILL_BLANK,
            QUIZ_MULTIPLE_CHOICE,
            QUIZ_ERROR_CORRECTION,
            QUIZ_REWRITE_NATURALLY,
            QUIZ_RANDOM,
            WEEKLY_TOPIC,
            WEEKLY_NARRATIVE,
            COACH_CHAT_AFTER_QUIZ,
            COACH_CHAT_AFTER_WRITING,
            COACH_THREAD_TITLE,
        }
    )

    # All grading/evaluation tasks (for deterministic settings)
    GRADING_TASKS = frozenset(
        {
            GRADE_QUIZ_ANSWER,
            MINI_WRITING_EVAL,
            WEEKLY_WRITING_EVAL,
        }
    )
