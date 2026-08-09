"""Writing database models."""

from datetime import datetime
from enum import Enum

from sqlmodel import JSON, Column, Field, SQLModel


class WritingPromptType(str, Enum):
    """Type of writing prompt."""

    MINI = "MINI"
    WEEKLY = "WEEKLY"


class WritingSubmissionType(str, Enum):
    """Type of writing submission."""

    MINI = "MINI"
    WEEKLY = "WEEKLY"


class WritingPrompt(SQLModel, table=True):
    """A writing prompt."""

    __tablename__ = "writing_prompt"

    id: int | None = Field(default=None, primary_key=True)
    prompt_type: WritingPromptType = Field(index=True)
    topic: str = Field(index=True)
    used_at: datetime = Field(default_factory=datetime.utcnow)
    week_id: int | None = Field(default=None, foreign_key="weekly_report.id", index=True)


class WritingSubmission(SQLModel, table=True):
    """A learner submission to a writing prompt."""

    __tablename__ = "writing_submission"

    id: int | None = Field(default=None, primary_key=True)
    prompt_id: int = Field(index=True, foreign_key="writing_prompt.id")
    submission_type: WritingSubmissionType = Field(index=True)
    submitted_text: str
    word_count: int
    created_at: datetime = Field(default_factory=datetime.utcnow)


class WritingEvaluation(SQLModel, table=True):
    """An evaluation of a writing submission."""

    __tablename__ = "writing_evaluation"

    id: int | None = Field(default=None, primary_key=True)
    submission_id: int = Field(index=True, foreign_key="writing_submission.id")

    # Numeric scores (0-100) - nullable for MINI tasks
    grammar_score: float | None = Field(default=None)
    naturalness_score: float | None = Field(default=None)
    vocabulary_score: float | None = Field(default=None)
    coherence_score: float | None = Field(default=None)
    overall_score: float | None = Field(default=None)

    # Structured feedback
    feedback_json: dict | None = Field(default=None, sa_column=Column(JSON))
    suggested_items_json: list | None = Field(default=None, sa_column=Column(JSON))

    # CEFR band (Part B - weekly evaluations only, None for mini)
    cefr_band: str | None = Field(default=None, index=True)
    cefr_justification: str | None = Field(default=None)

    # v1.1 evaluation metadata (ADR-13)
    evaluator_provider: str | None = Field(default=None)
    evaluator_model: str | None = Field(default=None)
    prompt_version: str | None = Field(default=None)
    rubric_version: str | None = Field(default=None)

    created_at: datetime = Field(default_factory=datetime.utcnow)
