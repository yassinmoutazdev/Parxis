"""Approval queue database model."""

from datetime import datetime
from enum import Enum
from typing import Any

from sqlmodel import JSON, Column, Field, SQLModel


class ApprovalSourceType(str, Enum):
    """Source type for approval queue items."""

    NOTE_PARSE = "NOTE_PARSE"
    WRITING_FEEDBACK = "WRITING_FEEDBACK"
    QUIZ_FEEDBACK = "QUIZ_FEEDBACK"


class ApprovalStatus(str, Enum):
    """Approval item status."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    EDITED_APPROVED = "EDITED_APPROVED"
    REJECTED = "REJECTED"


class ApprovalQueue(SQLModel, table=True):
    """Items waiting for learner approval."""

    __tablename__ = "approval_queue"

    id: int | None = Field(default=None, primary_key=True)
    source_type: ApprovalSourceType = Field(index=True)
    source_id: int = Field(index=True)
    item_type: str = Field(index=True)  # Mirrors ItemType, plus "CORRECTION"
    extracted_text: str
    explanation: str | None = Field(default=None)
    example_sentence: str | None = Field(default=None)
    source_context: str
    possible_duplicate_of: int | None = Field(
        default=None, foreign_key="learning_item.id", index=True
    )
    status: ApprovalStatus = Field(default=ApprovalStatus.PENDING, index=True)
    reviewed_payload: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    reviewed_at: datetime | None = Field(default=None)
