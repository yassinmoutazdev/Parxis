"""Source and Lesson database models."""

from datetime import datetime
from enum import Enum

from sqlmodel import Field, SQLModel


class SourceType(str, Enum):
    """Source type enumeration."""

    BOOK = "BOOK"
    OTHER = "OTHER"


class Source(SQLModel, table=True):
    """Learning source (e.g., a textbook)."""

    __tablename__ = "source"

    id: int | None = Field(default=None, primary_key=True)
    title: str = Field(index=True)
    author: str | None = Field(default=None)
    source_type: SourceType = Field(default=SourceType.OTHER)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Lesson(SQLModel, table=True):
    """A lesson within a source."""

    __tablename__ = "lesson"

    id: int | None = Field(default=None, primary_key=True)
    source_id: int | None = Field(default=None, foreign_key="source.id", index=True)
    title: str = Field(index=True)
    order_index: int | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
