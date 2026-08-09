"""Restrict quiz_mode to MULTIPLE_CHOICE only

This migration documents the Part A consolidation of QuizMode to MULTIPLE_CHOICE only.
The restriction is enforced at the application level (model default and service logic).
Database-level CHECK constraints are not added because historical rows with other
mode values remain as-is and are not backfilled (no destructive column changes).

Revision ID: 6_restrict_quiz_mode
Revises: 5_add_chat_tables
Create Date: 2026-08-09

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "6_restrict_quiz_mode"
down_revision: str | None = "5_add_chat_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # No database-level constraint changes - restriction enforced at application level
    # QuizMode enum in models/quiz.py only has MULTIPLE_CHOICE
    # QuizService.start_session only creates MULTIPLE_CHOICE questions
    # Historical rows with other mode values remain as-is (no backfill)
    pass


def downgrade() -> None:
    # No-op - application-level enforcement remains
    pass