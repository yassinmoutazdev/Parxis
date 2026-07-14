"""Learning Item and Tag database models."""

from datetime import datetime
from enum import Enum

from sqlmodel import Field, SQLModel


class ItemType(str, Enum):
    """Learning item type."""

    COLLOCATION = "COLLOCATION"
    IDIOM = "IDIOM"
    PHRASAL_VERB = "PHRASAL_VERB"
    GRAMMAR_NOTE = "GRAMMAR_NOTE"
    PERSONAL_EXAMPLE = "PERSONAL_EXAMPLE"


class LearningItem(SQLModel, table=True):
    """An approved learning item."""

    __tablename__ = "learning_item"

    id: int | None = Field(default=None, primary_key=True)
    item_type: ItemType = Field(index=True)
    text: str
    definition: str | None = Field(default=None)
    example_sentence: str | None = Field(default=None)
    source_note_id: int | None = Field(default=None, foreign_key="note.id", index=True)
    source_approval_id: int = Field(index=True, foreign_key="approval_queue.id")

    # Mastery and scheduling fields
    mastery_score: float = Field(default=0.3)
    review_count: int = Field(default=0)
    correct_count: int = Field(default=0)
    incorrect_count: int = Field(default=0)
    last_reviewed_at: datetime | None = Field(default=None)
    next_review_due: datetime | None = Field(default=None, index=True)
    ease_factor: float = Field(default=2.5)
    interval_days: int = Field(default=0)
    suspended: bool = Field(default=False)

    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class Tag(SQLModel, table=True):
    """A tag for categorizing learning items."""

    __tablename__ = "tag"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)


class LearningItemTag(SQLModel, table=True):
    """Many-to-many relationship between learning items and tags."""

    __tablename__ = "learning_item_tag"

    learning_item_id: int = Field(foreign_key="learning_item.id", primary_key=True)
    tag_id: int = Field(foreign_key="tag.id", primary_key=True)
