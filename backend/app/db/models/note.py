"""Note database model."""

from datetime import datetime
from enum import Enum

from sqlmodel import Field, SQLModel


class NoteStatus(str, Enum):
    """Note processing status.

    PENDING_APPROVAL removed (Part H) - there's no approval queue left to
    wait on. Notes go NEW -> PARSING -> PROCESSED (items auto-inserted or
    silently/conversationally resolved) or PARSE_FAILED.
    """

    NEW = "NEW"
    PARSING = "PARSING"
    PROCESSED = "PROCESSED"
    PARSE_FAILED = "PARSE_FAILED"


class NoteSource(str, Enum):
    """Where a note's content came from."""

    VAULT = "vault"
    CHAT = "chat"


class Note(SQLModel, table=True):
    """A note, either synced from the Obsidian vault or captured from chat.

    Part H: notes can now originate from a chat `save_note` tool call, not
    just the vault watcher. Chat-sourced notes have no file on disk, so their
    text lives directly in `content` and `vault_path` is left null.
    """

    __tablename__ = "note"

    id: int | None = Field(default=None, primary_key=True)
    source: NoteSource = Field(default=NoteSource.VAULT, index=True)
    vault_path: str | None = Field(default=None, unique=True, index=True)
    content: str | None = Field(default=None)  # raw text for chat-sourced notes
    content_hash: str
    lesson_id: int | None = Field(default=None, foreign_key="lesson.id", index=True)
    status: NoteStatus = Field(default=NoteStatus.NEW, index=True)
    changed_since_processed: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    processed_at: datetime | None = Field(default=None)
