"""Quiz database models."""

from datetime import datetime
from enum import Enum

from sqlmodel import Column, Field, JSON, SQLModel


class QuizScope(str, Enum):
    """Quiz scope."""

    AD_HOC = "AD_HOC"
    WEEKLY_REVIEW = "WEEKLY_REVIEW"


class QuizMode(str, Enum):
    """Quiz mode/types."""

    RECALL = "RECALL"
    FILL_BLANK = "FILL_BLANK"
    MULTIPLE_CHOICE = "MULTIPLE_CHOICE"
    ERROR_CORRECTION = "ERROR_CORRECTION"
    REWRITE_NATURALLY = "REWRITE_NATURALLY"
    CONVERSATION = "CONVERSATION"
    MINI_ESSAY = "MINI_ESSAY"
    RANDOM = "RANDOM"


class QuizSession(SQLModel, table=True):
    """A quiz session."""

    __tablename__ = "quiz_session"

    id: int | None = Field(default=None, primary_key=True)
    quiz_scope: QuizScope = Field(default=QuizScope.AD_HOC, index=True)
    quiz_mode: QuizMode = Field(default=QuizMode.RECALL, index=True)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = Field(default=None)
    week_id: int | None = Field(default=None, foreign_key="weekly_report.id", index=True)


class GradedBy(str, Enum):
    """How a quiz question was graded."""

    DETERMINISTIC = "DETERMINISTIC"
    LLM = "LLM"


class QuizQuestion(SQLModel, table=True):
    """A question within a quiz session."""

    __tablename__ = "quiz_question"

    id: int | None = Field(default=None, primary_key=True)
    quiz_session_id: int = Field(index=True, foreign_key="quiz_session.id")
    learning_item_id: int | None = Field(default=None, foreign_key="learning_item.id", index=True)
    question_type: QuizMode = Field(index=True)
    prompt: str
    correct_answer: str | None = Field(default=None)
    distractors_json: list[str] | None = Field(default=None, sa_column=Column(JSON))
    user_answer: str | None = Field(default=None)
    is_correct: bool | None = Field(default=None)
    score: float | None = Field(default=None)  # 0.0-1.0 for rubric-graded types
    feedback: str | None = Field(default=None)
    graded_by: GradedBy | None = Field(default=None)

    # v1.1 evaluation metadata (ADR-13)
    evaluator_provider: str | None = Field(default=None)
    evaluator_model: str | None = Field(default=None)
    prompt_version: str | None = Field(default=None)
    rubric_version: str | None = Field(default=None)

    created_at: datetime = Field(default_factory=datetime.utcnow)
