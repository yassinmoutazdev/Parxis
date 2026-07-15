"""Writing evaluation prompt templates.

Corresponds to ARCHITECTURE Sections 9.4 (Mini) and 9.5 (Weekly).
"""

# Prompt version constants (ADR-13)
MINI_WRITING_EVAL_PROMPT_VERSION = "1.0.0"
MINI_WRITING_EVAL_RUBRIC_VERSION = "1.0.0"
WEEKLY_WRITING_EVAL_PROMPT_VERSION = "1.0.0"
WEEKLY_WRITING_EVAL_RUBRIC_VERSION = "1.0.0"

# Rubric text blocks (separately versioned per ADR-13)
MINI_WRITING_EVAL_RUBRIC = """Evaluate the writing based on:

1. Grammar: Check for grammatical errors
2. Naturalness: Evaluate if the writing sounds natural for a native speaker
3. Vocabulary: Assess word choice appropriateness

Provide corrections for any errors found.
Limit naturalness_notes to 2 items maximum."""


WEEKLY_WRITING_EVAL_RUBRIC = """Evaluate the writing across five dimensions:

1. Grammar (0-100): Grammatical correctness and sentence structure
2. Naturalness (0-100): How natural the writing sounds
3. Vocabulary (0-100): Word choice and expression variety
4. Coherence (0-100): Logical flow and organization
5. Overall (0-100): General quality assessment

Provide specific feedback for each dimension."""


# Mini writing evaluation prompt
MINI_WRITING_EVAL_PROMPT = """You are a writing teacher. Evaluate the learner's mini writing submission.

Submission:
{submission_text}

{focus_areas}

{RUBRIC}

Generate your evaluation in JSON format:
{{
    "corrections": [
        {{"wrong": "the error", "correct": "the correction", "explanation": "why"}}
    ],
    "naturalness_notes": ["note 1", "note 2"],
    "suggested_items": []
}}

Important:
- Limit naturalness_notes to exactly 2 items
- suggested_items should be empty for mini writing (only for weekly)
Return valid JSON only."""


# Weekly writing evaluation prompt
WEEKLY_WRITING_EVAL_PROMPT = """You are a writing teacher. Evaluate the learner's weekly writing submission.

Submission:
{submission_text}

Weak areas to focus on:
{weak_categories}

Known relevant items from your knowledge base:
{known_relevant_items}

{RUBRIC}

Generate your evaluation in JSON format:
{{
    "grammar": {{"score": 85, "feedback": "Good grammar overall..."}},
    "naturalness": {{"score": 80, "feedback": "Sounds natural..."}},
    "vocabulary": {{"score": 75, "feedback": "Could use more varied vocabulary..."}},
    "coherence": {{"score": 90, "feedback": "Well organized..."}},
    "overall": {{"score": 82, "feedback": "Good effort..."}},
    "suggested_items": []
}}

Important:
- All scores must be between 0 and 100
- overall.feedback must be non-empty
Return valid JSON only."""


def get_mini_writing_eval_prompt() -> str:
    """Get the mini writing evaluation prompt template.

    Returns:
        The prompt template string with rubric substituted
    """
    return MINI_WRITING_EVAL_PROMPT.replace("{RUBRIC}", MINI_WRITING_EVAL_RUBRIC)


def get_weekly_writing_eval_prompt() -> str:
    """Get the weekly writing evaluation prompt template.

    Returns:
        The prompt template string with rubric substituted
    """
    return WEEKLY_WRITING_EVAL_PROMPT.replace("{RUBRIC}", WEEKLY_WRITING_EVAL_RUBRIC)


def get_mini_writing_eval_versions() -> tuple[str, str]:
    """Get prompt and rubric versions for mini writing evaluation.

    Returns:
        Tuple of (prompt_version, rubric_version)
    """
    return (MINI_WRITING_EVAL_PROMPT_VERSION, MINI_WRITING_EVAL_RUBRIC_VERSION)


def get_weekly_writing_eval_versions() -> tuple[str, str]:
    """Get prompt and rubric versions for weekly writing evaluation.

    Returns:
        Tuple of (prompt_version, rubric_version)
    """
    return (WEEKLY_WRITING_EVAL_PROMPT_VERSION, WEEKLY_WRITING_EVAL_RUBRIC_VERSION)
