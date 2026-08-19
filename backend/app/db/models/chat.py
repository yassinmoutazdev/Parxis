"""Chat database models."""

from datetime import datetime
from enum import Enum

from sqlmodel import Field, SQLModel


class ChatRole(str, Enum):
    """Chat message role."""

    USER = "USER"
    ASSISTANT = "ASSISTANT"
    SYSTEM = "SYSTEM"


class ChatActionType(str, Enum):
    """Chat action type for inline plugins."""

    NONE = "NONE"
    QUIZ = "QUIZ"
    WRITING = "WRITING"


class ChatThread(SQLModel, table=True):
    """A chat thread."""

    __tablename__ = "chat_thread"

    id: int | None = Field(default=None, primary_key=True)
    title: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_message_preview: str | None = Field(default=None)
    history_summary: str | None = Field(default=None)
    summarized_up_to_message_id: int | None = Field(default=None)


class ChatMessage(SQLModel, table=True):
    """A message within a chat thread."""

    __tablename__ = "chat_message"

    id: int | None = Field(default=None, primary_key=True)
    thread_id: int = Field(index=True, foreign_key="chat_thread.id")
    role: ChatRole
    content: str
    action_type: ChatActionType = Field(default=ChatActionType.NONE)
    action_ref_id: int | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class AttachmentKind(str, Enum):
    """Kind of chat message attachment."""

    TEXT = "text"
    IMAGE = "image"


class ChatMessageAttachment(SQLModel, table=True):
    """An ephemeral file attached to a single chat message.

    Attachments are context for that one conversation turn only -- they are
    NOT fed into the vault-watcher/ingestion pipeline and never produce
    learning_item/learning_correction/tracked note records.
    """

    __tablename__ = "chat_message_attachment"

    id: int | None = Field(default=None, primary_key=True)
    message_id: int = Field(index=True, foreign_key="chat_message.id")
    filename: str
    mime_type: str
    kind: AttachmentKind
    extracted_text: str | None = Field(default=None)
    stored_path: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
