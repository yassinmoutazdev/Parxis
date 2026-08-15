"""Learning Correction database model (v1.1 - split from Correction)."""

from datetime import datetime

from sqlmodel import Field, SQLModel


class LearningCorrection(SQLModel, table=True):
    """A correction extracted from notes or writing feedback.

    New knowledge extracted from a note or a writing-feedback suggestion
    (e.g. 'I used to say X, the correct/more natural form is Y').
    Auto-screened (Part H) - not approval-gated. Structurally identical in
    spirit to LearningItem.
    """

    __tablename__ = "learning_correction"

    id: int | None = Field(default=None, primary_key=True)
    wrong_form: str
    correct_form: str
    explanation: str | None = Field(default=None)
    example_sentence: str | None = Field(default=None)
    source_note_id: int | None = Field(default=None, foreign_key="note.id", index=True)
    source_writing_evaluation_id: int | None = Field(
        default=None, foreign_key="writing_evaluation.id", index=True
    )

    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
