"""Weekly report prompt templates.

Corresponds to ARCHITECTURE Sections 9.6 (Narrative) and 9.7 (Topic Generation).
"""

# Prompt version constants (ADR-13)
WEEKLY_NARRATIVE_PROMPT_VERSION = "1.0.0"
WEEKLY_TOPIC_PROMPT_VERSION = "1.0.0"

# Weekly narrative generation prompt
WEEKLY_NARRATIVE_PROMPT = """Generate a weekly learning narrative report.

Context:
- Items studied this week: {items_studied}
- Quiz performance: {quiz_performance}
- Writing submissions: {writing_submissions}
- Time spent: {time_spent}

Generate a narrative report in JSON format:
{{
    "narrative_report": "Your 150-300 word narrative about the week's learning...",
    "top_strengths_this_week": ["strength 1", "strength 2", "strength 3"],
    "top_focus_areas_next_week": ["area 1", "area 2", "area 3"]
}}

Important:
- narrative_report should be 150-300 words
- Provide exactly 3 strengths and 3 focus areas
Return valid JSON only."""


# Weekly topic generation prompt
WEEKLY_TOPIC_PROMPT = """Generate a topic for the learner's weekly writing practice.

Context:
- Recent topics (exclude these): {recent_topics}
- Learner level: {learner_level}
- Weak areas: {weak_areas}

Generate a topic in JSON format:
{{
    "topic": "A specific topic title",
    "prompt_text": "Write about [topic] in 150-200 words..."
}}

Important:
- topic must not be a substring of any recent topics
- prompt_text should guide the learner appropriately for their level
Return valid JSON only."""


def get_weekly_narrative_prompt() -> str:
    """Get the weekly narrative prompt template.

    Returns:
        The prompt template string
    """
    return WEEKLY_NARRATIVE_PROMPT


def get_weekly_topic_prompt() -> str:
    """Get the weekly topic prompt template.

    Returns:
        The prompt template string
    """
    return WEEKLY_TOPIC_PROMPT


def get_weekly_narrative_version() -> str:
    """Get the version for weekly narrative prompt.

    Returns:
        The prompt version string
    """
    return WEEKLY_NARRATIVE_PROMPT_VERSION


def get_weekly_topic_version() -> str:
    """Get the version for weekly topic prompt.

    Returns:
        The prompt version string
    """
    return WEEKLY_TOPIC_PROMPT_VERSION
