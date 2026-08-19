"""Add history_summary and summarized_up_to_message_id to chat_thread

Revision ID: 9_add_chat_thread_summary
Revises: 8_add_chat_message_attachment
Create Date: 2026-08-19

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "9_add_chat_thread_summary"
down_revision: str | None = "8_add_chat_message_attachment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "chat_thread", sa.Column("history_summary", sa.String(), nullable=True)
    )
    op.add_column(
        "chat_thread",
        sa.Column("summarized_up_to_message_id", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("chat_thread", "summarized_up_to_message_id")
    op.drop_column("chat_thread", "history_summary")
