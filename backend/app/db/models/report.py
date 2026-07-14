"""Weekly Report database model."""

from datetime import date, datetime

from sqlmodel import JSON, Column, Field, SQLModel


class WeeklyReport(SQLModel, table=True):
    """A weekly progress report."""

    __tablename__ = "weekly_report"

    id: int | None = Field(default=None, primary_key=True)
    week_start: date = Field(unique=True, index=True)
    week_end: date = Field(index=True)
    items_studied_count: int = Field(default=0)

    # Aggregated data
    quiz_summary_json: dict | None = Field(default=None, sa_column=Column(JSON))
    mini_writing_summary_json: dict | None = Field(default=None, sa_column=Column(JSON))

    # Weekly writing evaluation
    weekly_writing_evaluation_id: int | None = Field(
        default=None, foreign_key="writing_evaluation.id", index=True
    )

    # Mastery snapshot
    mastery_snapshot_json: dict | None = Field(default=None, sa_column=Column(JSON))

    # LLM-generated narrative
    narrative_report: str | None = Field(default=None)

    created_at: datetime = Field(default_factory=datetime.utcnow)
