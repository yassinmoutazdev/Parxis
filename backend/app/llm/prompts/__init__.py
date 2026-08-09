"""Prompt templates for LLM tasks.

This module provides a unified interface for accessing all prompt templates.
Each task has its own module with co-located version constants per ADR-13.
"""

from app.llm.interface import TaskType

from . import coach, parser, quiz, weekly_report, writing_eval

# Prompt template lookup
_PROMPT_TEMPLATES: dict[str, str] = {
    # Parser
    TaskType.PARSE_NOTE: parser.get_parse_note_prompt(),
    # Quiz generation
    TaskType.QUIZ_MULTIPLE_CHOICE: quiz.get_quiz_prompt(TaskType.QUIZ_MULTIPLE_CHOICE),
    # Writing evaluation
    TaskType.MINI_WRITING_EVAL: writing_eval.get_mini_writing_eval_prompt(),
    TaskType.WEEKLY_WRITING_EVAL: writing_eval.get_weekly_writing_eval_prompt(),
    # Weekly reports
    TaskType.WEEKLY_NARRATIVE: weekly_report.get_weekly_narrative_prompt(),
    TaskType.WEEKLY_TOPIC: weekly_report.get_weekly_topic_prompt(),
    # Chat coach follow-ups (still JSON-schema based; the main coach_chat
    # turn uses tool-calling directly via generate_chat_with_tools instead
    # of get_prompt_template)
    TaskType.COACH_CHAT_AFTER_QUIZ: coach.COACH_CHAT_AFTER_QUIZ_PROMPT,
    TaskType.COACH_CHAT_AFTER_WRITING: coach.COACH_CHAT_AFTER_WRITING_PROMPT,
    TaskType.COACH_THREAD_TITLE: coach.COACH_THREAD_TITLE_PROMPT,
}


def get_prompt_template(task: str) -> str:
    """Get the prompt template for a given task.

    Args:
        task: The task identifier (e.g., 'parse_note', 'quiz_recall')

    Returns:
        The prompt template string

    Raises:
        KeyError: If no template exists for the task
    """
    if task not in _PROMPT_TEMPLATES:
        raise KeyError(f"No prompt template found for task: {task}")
    return _PROMPT_TEMPLATES[task]