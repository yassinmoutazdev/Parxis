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
    definition: str | None = None
    example_sentence: str | None = None
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
    feedback: str = Field(min_length=1, description="1-2 sentences")


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
    """

    grammar: DimensionScore
    naturalness: DimensionScore
    vocabulary: DimensionScore
    coherence: DimensionScore
    overall: DimensionScore
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
