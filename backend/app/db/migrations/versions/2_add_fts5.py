"""Add FTS5 virtual table for learning_item search

Revision ID: 2_add_fts5
Revises: c1e186e4d709
Create Date: 2026-07-14

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2_add_fts5"
down_revision: str | None = "c1e186e4d709"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create FTS5 virtual table
    op.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS learning_item_fts USING fts5(
            text,
            definition,
            content='learning_item',
            content_rowid='id'
        )
    """)

    # Create triggers to keep FTS5 in sync with learning_item table

    # Trigger for INSERT - use shorter column ref
    op.execute("""
        CREATE TRIGGER IF NOT EXISTS learning_item_ai
        AFTER INSERT ON learning_item BEGIN
            INSERT INTO learning_item_fts(rowid, text, definition)
            VALUES (new.id, new.text, new.definition);
        END
    """)

    # Trigger for DELETE
    op.execute("""
        CREATE TRIGGER IF NOT EXISTS learning_item_ad
        AFTER DELETE ON learning_item BEGIN
            INSERT INTO learning_item_fts(learning_item_fts, rowid, text, definition)
            VALUES ('delete', old.id, old.text, old.definition);
        END
    """)

    # Trigger for UPDATE
    op.execute("""
        CREATE TRIGGER IF NOT EXISTS learning_item_au
        AFTER UPDATE ON learning_item BEGIN
            INSERT INTO learning_item_fts(learning_item_fts, rowid, text, definition)
            VALUES ('delete', old.id, old.text, old.definition);
            INSERT INTO learning_item_fts(rowid, text, definition)
            VALUES (new.id, new.text, new.definition);
        END
    """)


def downgrade() -> None:
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS learning_item_ai")
    op.execute("DROP TRIGGER IF EXISTS learning_item_ad")
    op.execute("DROP TRIGGER IF EXISTS learning_item_au")

    # Drop FTS5 table
    op.execute("DROP TABLE IF EXISTS learning_item_fts")
