"""Note database model."""

from datetime import datetime
from enum import Enum

from sqlmodel import Field, SQLModel


class NoteStatus(str, Enum):
    """Note processing status."""

    NEW = "NEW"
    PARSING = "PARSING"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    PROCESSED = "PROCESSED"
    PARSE_FAILED = "PARSE_FAILED"


class Note(SQLModel, table=True):
    """A note from the Obsidian vault."""

    __tablename__ = "note"

    id: int | None = Field(default=None, primary_key=True)
    vault_path: str = Field(unique=True, index=True)
    content_hash: str
    lesson_id: int | None = Field(default=None, foreign_key="lesson.id", index=True)
    status: NoteStatus = Field(default=NoteStatus.NEW, index=True)
    changed_since_processed: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    processed_at: datetime | None = Field(default=None)
