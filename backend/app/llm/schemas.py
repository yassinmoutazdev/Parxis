"""LLM output schemas (Pydantic models).

This module defines all output schemas for LLM interactions.
Each schema is used with Ollama's `format` parameter for structured output.
"""

from typing import Literal

from pydantic import BaseModel, Field

# =============================================================================
# Parser Schemas (Section 9.1)
# =============================================================================


class ParsedItem(BaseModel):
    """A single parsed item extracted from a note.

    Corresponds to ARCHITECTURE Section 9.1 (Parser Output schema).
    Updated per Part E: confidence field, required definition/example_sentence
    (except CORRECTION), possible_duplicate_reason for semantic redundancy.
    """

    item_type: Literal[
        "COLLOCATION",
        "IDIOM",
        "PHRASAL_VERB",
        "GRAMMAR_NOTE",
        "PERSONAL_EXAMPLE",
        "CORRECTION",
    ]
    text: str
    definition: str | None = None  # Required for non-CORRECTION types (validated in validation.py)
    example_sentence: str | None = None  # Required for non-CORRECTION types (validated in validation.py)
    source_excerpt: str = Field(
        description="verbatim span from note_content this was drawn from"
    )
    wrong_form: str | None = Field(
        default=None,
        description="only for CORRECTION item_type",
    )
    correct_form: str | None = Field(
        default=None,
        description="only for CORRECTION item_type",
    )
    confidence: Literal["high", "medium", "low"] = Field(
        default="medium",
        description="Model's self-reported confidence in this extraction",
    )
    low_confidence_reason: str | None = Field(
        default=None,
        description=(
            "Only populated when confidence == 'low'. What specifically is "
            "uncertain (ambiguous sense, idiomatic vs. literal, unclear "
            "register, etc.) - not a generic 'not sure'. Reused verbatim as "
            "both the retry correction instruction and, for chat-sourced "
            "items still unresolved after retry, the clarifying question "
            "asked back to the user."
        ),
    )
    possible_duplicate_reason: str | None = Field(
        default=None,
        description="If model suspects semantic overlap with recent_items_section, explain why",
    )


class ParsedNoteOutput(BaseModel):
    """Output schema for parse_note task.

    Corresponds to ARCHITECTURE Section 9.1 (ParsedNoteOutput).
    """

    items: list[ParsedItem]


# =============================================================================
# Quiz Schemas (Sections 9.2, 9.3)
# =============================================================================


class QuizQuestionOutput(BaseModel):
    """Output schema for quiz generation tasks.

    Corresponds to ARCHITECTURE Section 9.2 (QuizQuestionOutput).
    """

    prompt_text: str
    correct_answer: str | None = Field(
        default=None,
        description="null for open-ended modes (rewrite/conversation/mini_essay)",
    )
    distractors: list[str] | None = Field(
        default=None,
        description="multiple_choice only, exactly 3 required",
    )


class GradedAnswerOutput(BaseModel):
    """Output schema for quiz answer grading (LLM fallback path).

    Corresponds to ARCHITECTURE Section 9.3 (GradedAnswerOutput).
    Note: score uses plain float (no ge/le) because constrained decoding
    enforces shape, not numeric range. Defensive re-clamping happens in
    validation.py.
    """

    score: float = Field(description="0.0-1.0")


# =============================================================================
# Writing Evaluation Schemas (Sections 9.4, 9.5)
# =============================================================================


class InlineCorrection(BaseModel):
    """A single inline correction for mini writing evaluation.

    Corresponds to ARCHITECTURE Section 9.4 (InlineCorrection).
    """

    wrong: str
    correct: str
    explanation: str


class MiniWritingEvalOutput(BaseModel):
    """Output schema for mini writing evaluation task.

    Corresponds to ARCHITECTURE Section 9.4 (MiniWritingEvalOutput).
    """

    corrections: list[InlineCorrection] = Field(default_factory=list)
    naturalness_notes: list[str] = Field(
        default_factory=list,
        description="capped at 2 by prompt instruction; enforced by truncation if the model over-produces",
    )
    suggested_items: list[ParsedItem] = Field(default_factory=list)


class DimensionScore(BaseModel):
    """A single dimension score for weekly writing evaluation.

    Corresponds to ARCHITECTURE Section 9.5 (DimensionScore).
    Note: score uses plain float (no ge/le) because constrained decoding
    enforces shape, not numeric range. Defensive re-clamping happens in
    validation.py.
    """

    score: float = Field(description="0-100")
    feedback: str


class WeeklyWritingEvalOutput(BaseModel):
    """Output schema for weekly writing evaluation task.

    Corresponds to ARCHITECTURE Section 9.5 (WeeklyWritingEvalOutput).
    Updated for CEFR banding (Part B).
    """

    cefr_band: Literal["A1", "A2", "B1", "B2", "C1", "C2"]
    band_justification: str = Field(description="Specific justification referencing text features")
    grammar: DimensionScore
    naturalness: DimensionScore
    vocabulary: DimensionScore
    coherence: DimensionScore
    suggested_items: list[ParsedItem] = Field(default_factory=list)


# =============================================================================
# Report Schemas (Sections 9.6, 9.7)
# =============================================================================


class WeeklyNarrativeOutput(BaseModel):
    """Output schema for weekly report narrative generation.

    Corresponds to ARCHITECTURE Section 9.6 (WeeklyNarrativeOutput).
    """

    narrative_report: str = Field(
        description="150-300 words, soft-enforced by prompt"
    )
    top_strengths_this_week: list[str]
    top_focus_areas_next_week: list[str]


class TopicOutput(BaseModel):
    """Output schema for weekly topic generation.

    Corresponds to ARCHITECTURE Section 9.7 (TopicOutput).
    """

    topic: str
    prompt_text: str = Field(
        description="the actual instruction shown to the learner"
    )


# =============================================================================
# Chat Coach Schemas (Section 4.1)
# =============================================================================


class CoachFollowupReply(BaseModel):
    """Output schema for the after-quiz / after-writing follow-up tasks.

    These follow-ups never trigger tools (the action already happened), so
    they stay on the simple JSON-schema path rather than tool-calling.

    Corresponds to PRAXIS_CHAT_COACH_PLAN Section 4.1 (refactored per ADR:
    main coach_chat turn moved to tool-calling; follow-ups unaffected).
    """

    reply_text: str = Field(
        description="the assistant's conversational follow-up reply"
    )


class CoachThreadTitle(BaseModel):
    """Output schema for the coach_thread_title task.

    Generated via a small separate LLM call after the first assistant reply
    in a new thread, since replies are now plain text (no forced JSON) under
    tool-calling and can no longer carry a `suggested_thread_title` field
    inline.
    """

    title: str = Field(description="a 3-6 word chat title")


class CoachHistorySummary(BaseModel):
    """Output schema for the coach_chat_summarize task."""

    summary: str
