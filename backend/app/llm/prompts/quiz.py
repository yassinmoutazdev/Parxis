"""Quiz generation prompt templates.

Corresponds to ARCHITECTURE Section 9.2 (Quiz Generator).
"""

# Version constant for MULTIPLE_CHOICE quiz mode (ADR-13)
QUIZ_MULTIPLE_CHOICE_PROMPT_VERSION = "2.0.0"

# Prompt template for multiple choice quiz mode
QUIZ_MULTIPLE_CHOICE_PROMPT = """You are building one multiple-choice question to test whether the learner
can use the following item correctly and naturally in English -- not just
recognize its definition.

Learning item:
{item_text}
Definition: {item_definition}
Example usage: {item_example}

Write a question (a sentence with a blank, or a short natural-usage
scenario) whose correct answer requires understanding how this item is
actually used -- register, collocation, tense, or common confusion with
a near-synonym -- not just matching a dictionary definition.

Then write exactly 3 distractors. Distractors must be:
- Plausible to someone with partial understanding (not obviously wrong)
- Wrong for a specific, describable reason (wrong register, wrong
  collocation, wrong tense/form, or a common confusable word) --
  avoid distractors that are simply unrelated words
- Each wrong for a different reason where possible, so the question
  probes more than one kind of mistake

Return JSON:
{{
    "prompt_text": "...",
    "correct_answer": "...",
    "distractors": ["...", "...", "..."]
}}
Return valid JSON only."""


def get_quiz_prompt(task: str) -> str:
    """Get the quiz prompt template for a given task.

    Args:
        task: The quiz task identifier (e.g., 'quiz_multiple_choice')

    Returns:
        The prompt template string
    """
    if task == "quiz_multiple_choice":
        return QUIZ_MULTIPLE_CHOICE_PROMPT
    return ""


def get_quiz_prompt_version(task: str) -> str:
    """Get the version constant for a quiz prompt.

    Args:
        task: The quiz task identifier

    Returns:
        The prompt version string
    """
    if task == "quiz_multiple_choice":
        return QUIZ_MULTIPLE_CHOICE_PROMPT_VERSION
    return "1.0.0"