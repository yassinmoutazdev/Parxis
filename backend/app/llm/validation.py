"""Semantic validation functions for LLM outputs.

Corresponds to ARCHITECTURE Section 9's per-task validation rules.

These functions perform semantic validation beyond what the Pydantic schemas
(grammar-constrained via `format` parameter) can enforce.
"""

import logging
from typing import Any

from app.llm.schemas import (
    GradedAnswerOutput,
    MiniWritingEvalOutput,
    ParsedNoteOutput,
    QuizQuestionOutput,
    WeeklyNarrativeOutput,
    WeeklyWritingEvalOutput,
    DimensionScore,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Parser Validation (Section 9.1)
# =============================================================================


def validate_parsed_note(
    output: ParsedNoteOutput,
    note_content: str,
) -> tuple[ParsedNoteOutput, list[str]]:
    """Validate parsed note output.

    Corresponds to ARCHITECTURE Section 9.1 (Validation rules) + Part E:
    - source_excerpt must be a substring of note_content
    - CORRECTION items must have both wrong_form and correct_form
    - Non-CORRECTION items must have definition and example_sentence
    - confidence must be present (validated by schema)
    - possible_duplicate_reason is optional metadata

    Args:
        output: The parsed note output
        note_content: The original note content

    Returns:
        Tuple of (potentially modified output, list of warnings)
    """
    warnings: list[str] = []
    items = output.items

    for i, item in enumerate(items):
        # Check source_excerpt is substring of note_content
        if item.source_excerpt and item.source_excerpt not in note_content:
            warnings.append(
                f"Item {i}: source_excerpt is not a verbatim quote from note"
            )

        # For CORRECTION type, ensure both fields are present
        if item.item_type == "CORRECTION":
            if not item.wrong_form or not item.correct_form:
                warnings.append(
                    f"Item {i}: CORRECTION missing wrong_form or correct_form"
                )
                # Downgrade to PERSONAL_EXAMPLE per architecture
                item.item_type = "PERSONAL_EXAMPLE"
                item.wrong_form = None
                item.correct_form = None
        else:
            # Non-CORRECTION types: definition and example_sentence are required
            if not item.definition or not item.definition.strip():
                warnings.append(
                    f"Item {i} ({item.item_type}): missing required definition"
                )
            if not item.example_sentence or not item.example_sentence.strip():
                warnings.append(
                    f"Item {i} ({item.item_type}): missing required example_sentence"
                )

        # Confidence is validated by schema (Literal["high", "medium", "low"])
        # possible_duplicate_reason is optional metadata - no validation needed

    return output, warnings


# =============================================================================
# Quiz Validation (Section 9.2)
# =============================================================================


def validate_quiz_question(
    output: QuizQuestionOutput,
) -> tuple[QuizQuestionOutput | None, list[str]]:
    """Validate quiz question output (multiple choice only).

    Corresponds to ARCHITECTURE Section 9.2 (Validation rules):
    - multiple_choice: distractors must have exactly 3 entries

    Args:
        output: The quiz question output

    Returns:
        Tuple of (None if invalid with error in warnings, or output)
    """
    warnings: list[str] = []

    # MC: exactly 3 distractors, none equal to correct_answer
    if not output.distractors or len(output.distractors) != 3:
        warnings.append("multiple_choice requires exactly 3 distractors")
        return None, warnings

    if output.correct_answer:
        for d in output.distractors:
            if d.lower() == output.correct_answer.lower():
                warnings.append("distractor matches correct_answer")
                return None, warnings

    return output, warnings


# =============================================================================
# Quiz Grading Validation (Section 9.3)
# =============================================================================


def validate_graded_answer(output: GradedAnswerOutput) -> GradedAnswerOutput:
    """Validate and clamp quiz answer grading output.

    Corresponds to ARCHITECTURE Section 9.3 (Validation):
    - score must be in [0.0, 1.0], re-clamped defensively

    Args:
        output: The graded answer output

    Returns:
        Output with score re-clamped to [0.0, 1.0]
    """
    # Defensive re-clamp per architecture (constrained decoding enforces
    # shape, not numeric range)
    output.score = max(0.0, min(1.0, output.score))
    return output


# =============================================================================
# Mini Writing Evaluation Validation (Section 9.4)
# =============================================================================


def validate_mini_writing_eval(
    output: MiniWritingEvalOutput,
) -> MiniWritingEvalOutput:
    """Validate and truncate mini writing evaluation output.

    Corresponds to ARCHITECTURE Section 9.4 (Validation):
    - naturalness_notes truncated to 2 items post-hoc

    Args:
        output: The mini writing evaluation output

    Returns:
        Output with naturalness_notes truncated to max 2 items
    """
    # Hard cap on naturalness_notes per architecture
    if len(output.naturalness_notes) > 2:
        output.naturalness_notes = output.naturalness_notes[:2]
        logger.info("Truncated naturalness_notes to 2 items")

    return output


# =============================================================================
# Weekly Writing Evaluation Validation (Section 9.5)
# =============================================================================


def validate_weekly_writing_eval(
    output: WeeklyWritingEvalOutput,
) -> tuple[WeeklyWritingEvalOutput, list[str]]:
    """Validate and clamp weekly writing evaluation output.

    Corresponds to ARCHITECTURE Section 9.5 (Validation) + Part B CEFR banding:
    - All four score values in [0, 100], re-clamped defensively
    - cefr_band must be valid (enforced by schema Literal)
    - band_justification must be non-empty

    Args:
        output: The weekly writing evaluation output

    Returns:
        Tuple of (validated output, list of warnings)
    """
    warnings: list[str] = []
    dimensions = [
        output.grammar,
        output.naturalness,
        output.vocabulary,
        output.coherence,
    ]

    for dim in dimensions:
        # Defensive re-clamp to [0, 100]
        dim.score = max(0.0, min(100.0, dim.score))

    # Check band_justification is non-empty
    if not output.band_justification or not output.band_justification.strip():
        warnings.append("band_justification must be non-empty")

    return output, warnings


# =============================================================================
# Weekly Narrative Validation (Section 9.6)
# =============================================================================


def validate_weekly_narrative(
    output: WeeklyNarrativeOutput,
) -> tuple[WeeklyNarrativeOutput, list[str]]:
    """Validate weekly narrative output.

    Corresponds to ARCHITECTURE Section 9.6 (Validation):
    - Word count checked post-hoc; outside 100-400 words logged as quality warning

    Args:
        output: The weekly narrative output

    Returns:
        Tuple of (output, list of warnings)
    """
    warnings: list[str] = []

    word_count = len(output.narrative_report.split())

    if word_count < 100 or word_count > 400:
        warnings.append(
            f"narrative_report word count ({word_count}) outside 100-400 range"
        )
        # Not a hard failure - still usable per architecture

    return output, warnings


# =============================================================================
# Topic Generation Validation (Section 9.7)
# =============================================================================


def validate_topic(
    output: Any,
    recent_topics: list[str],
) -> tuple[Any, list[str]]:
    """Validate topic output against recent topics.

    Corresponds to ARCHITECTURE Section 9.7 (Validation):
    - topic must not fuzzy-match (case-insensitive substring) any recent topics
    - On match, one retry with the offending topic excluded

    Args:
        output: The topic output (TopicOutput)
        recent_topics: List of recent topics to check against

    Returns:
        Tuple of (output, list of warnings)
    """
    warnings: list[str] = []

    topic_lower = output.topic.lower()

    for recent in recent_topics:
        if recent.lower() in topic_lower or topic_lower in recent.lower():
            warnings.append(
                f"topic '{output.topic}' matches recent topic '{recent}'"
            )
            return output, warnings

    return output, warnings


# =============================================================================
# Unified Validation Entry Point
# =============================================================================


def validate_output(
    task: str,
    output: Any,
    context: dict[str, Any] | None = None,
) -> tuple[Any, list[str]]:
    """Validate LLM output based on task type.

    Args:
        task: The task identifier
        output: The LLM output to validate
        context: Optional context for validation (e.g., note_content)

    Returns:
        Tuple of (validated output, list of warnings)
    """
    warnings: list[str] = []

    if task == "parse_note":
        note_content = context.get("note_content", "") if context else ""
        output, warnings = validate_parsed_note(output, note_content)

    elif task == "quiz_multiple_choice":
        output, warnings = validate_quiz_question(output)

    elif task == "mini_writing_eval":
        output = validate_mini_writing_eval(output)

    elif task == "weekly_writing_eval":
        output, warnings = validate_weekly_writing_eval(output)

    elif task == "weekly_narrative":
        output, warnings = validate_weekly_narrative(output)

    elif task == "weekly_topic":
        recent_topics = context.get("recent_topics", []) if context else []
        output, warnings = validate_topic(output, recent_topics)

    return output, warnings
