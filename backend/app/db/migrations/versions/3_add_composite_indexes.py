"""Add composite indexes

Revision ID: 3_add_composite_indexes
Revises: 2_add_fts5
Create Date: 2026-07-14

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3_add_composite_indexes"
down_revision: str | None = "2_add_fts5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Composite index on learning_item (item_type, suspended)
    op.create_index(
        "idx_learning_item_type_suspended",
        "learning_item",
        ["item_type", "suspended"],
        unique=False,
    )

    # Composite index on performance_error (source_type, source_id)
    op.create_index(
        "idx_perf_error_source", "performance_error", ["source_type", "source_id"], unique=False
    )

    # Composite index on performance_error (learning_item_id, created_at)
    op.create_index(
        "idx_perf_error_item_created",
        "performance_error",
        ["learning_item_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_perf_error_item_created", table_name="performance_error")
    op.drop_index("idx_perf_error_source", table_name="performance_error")
    op.drop_index("idx_learning_item_type_suspended", table_name="learning_item")
