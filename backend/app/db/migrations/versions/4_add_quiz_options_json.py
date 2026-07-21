"""Add quiz options_json column

Revision ID: 4_add_quiz_options_json
Revises: 3_add_composite_indexes
Create Date: 2026-07-21

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "4_add_quiz_options_json"
down_revision: str | None = "3_add_composite_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "quiz_question", sa.Column("options_json", sa.JSON(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("quiz_question", "options_json")