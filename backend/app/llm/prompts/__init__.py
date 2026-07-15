"""Prompt templates for LLM tasks.

This module provides a unified interface for accessing all prompt templates.
Each task has its own module with co-located version constants per ADR-13.
"""

from app.llm.interface import TaskType

from . import parser, quiz, weekly_report, writing_eval

# Quiz answer grading prompt (inline since it's simple)
_GRADE_QUIZ_ANSWER_PROMPT = """Grade the learner's quiz answer.

Question: {question_prompt}
Expected answer: {expected_answer}
Learner's answer: {learner_answer}

Generate your grading in JSON format:
{{
    "score": 0.85,
    "feedback": "Your answer is close but..."
}}

Important:
- score must be between 0.0 and 1.0
- feedback should be 1-2 sentences
Return valid JSON only."""

# Prompt template lookup
_PROMPT_TEMPLATES: dict[str, str] = {
    # Parser
    TaskType.PARSE_NOTE: parser.get_parse_note_prompt(),
    # Quiz generation
    TaskType.QUIZ_RECALL: quiz.get_quiz_prompt(TaskType.QUIZ_RECALL),
    TaskType.QUIZ_FILL_BLANK: quiz.get_quiz_prompt(TaskType.QUIZ_FILL_BLANK),
    TaskType.QUIZ_MULTIPLE_CHOICE: quiz.get_quiz_prompt(TaskType.QUIZ_MULTIPLE_CHOICE),
    TaskType.QUIZ_ERROR_CORRECTION: quiz.get_quiz_prompt(TaskType.QUIZ_ERROR_CORRECTION),
    TaskType.QUIZ_REWRITE_NATURALLY: quiz.get_quiz_prompt(TaskType.QUIZ_REWRITE_NATURALLY),
    TaskType.QUIZ_CONVERSATION: quiz.get_quiz_prompt(TaskType.QUIZ_CONVERSATION),
    TaskType.QUIZ_MINI_ESSAY: quiz.get_quiz_prompt(TaskType.QUIZ_MINI_ESSAY),
    # Quiz grading
    TaskType.GRADE_QUIZ_ANSWER: _GRADE_QUIZ_ANSWER_PROMPT,
    # Writing evaluation
    TaskType.MINI_WRITING_EVAL: writing_eval.get_mini_writing_eval_prompt(),
    TaskType.WEEKLY_WRITING_EVAL: writing_eval.get_weekly_writing_eval_prompt(),
    # Weekly reports
    TaskType.WEEKLY_NARRATIVE: weekly_report.get_weekly_narrative_prompt(),
    TaskType.WEEKLY_TOPIC: weekly_report.get_weekly_topic_prompt(),
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
