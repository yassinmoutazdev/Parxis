"""Add chat tables

Revision ID: 5_add_chat_tables
Revises: 4_add_quiz_options_json
Create Date: 2026-07-23

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "5_add_chat_tables"
down_revision: str | None = "4_add_quiz_options_json"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create chat_thread table
    op.create_table(
        "chat_thread",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("last_message_preview", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create chat_message table
    op.create_table(
        "chat_message",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("thread_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", sa.String(), nullable=False),
        sa.Column("action_type", sa.String(), nullable=False, server_default="NONE"),
        sa.Column("action_ref_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["thread_id"], ["chat_thread.id"]),
    )

    # Create indexes
    op.create_index("ix_chat_message_thread_id", "chat_message", ["thread_id"])
    op.create_index("ix_chat_message_created_at", "chat_message", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_chat_message_created_at", table_name="chat_message")
    op.drop_index("ix_chat_message_thread_id", table_name="chat_message")
    op.drop_table("chat_message")
    op.drop_table("chat_thread")
