"""Performance Error database model (v1.1 - split from Correction)."""

from datetime import datetime
from enum import Enum

from sqlmodel import Field, SQLModel


class PerformanceErrorSource(str, Enum):
    """Source type for performance errors."""

    QUIZ = "QUIZ"
    WRITING_MINI = "WRITING_MINI"
    WRITING_WEEKLY = "WRITING_WEEKLY"


class PerformanceError(SQLModel, table=True):
    """A record that a specific mistake happened during a quiz or writing task.

    Written directly by QuizService/WritingService at grading time — no approval
    step, no status/lifecycle. This is a factual record of something that
    already occurred.
    """

    __tablename__ = "performance_error"

    id: int | None = Field(default=None, primary_key=True)
    learning_item_id: int | None = Field(default=None, foreign_key="learning_item.id", index=True)
    wrong_form: str
    correct_form: str
    explanation: str | None = Field(default=None)
    source_type: PerformanceErrorSource = Field(index=True)
    source_id: int = Field(index=True)

    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
