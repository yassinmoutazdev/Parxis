"""Add chat_message_attachment table

Revision ID: 8_add_chat_message_attachment
Revises: 7_remove_approval_queue
Create Date: 2026-08-15

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "8_add_chat_message_attachment"
down_revision: str | None = "7_remove_approval_queue"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chat_message_attachment",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("mime_type", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("extracted_text", sa.String(), nullable=True),
        sa.Column("stored_path", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["message_id"], ["chat_message.id"]),
    )

    op.create_index(
        "ix_chat_message_attachment_message_id",
        "chat_message_attachment",
        ["message_id"],
    )
    op.create_index(
        "ix_chat_message_attachment_created_at",
        "chat_message_attachment",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_chat_message_attachment_created_at", table_name="chat_message_attachment"
    )
    op.drop_index(
        "ix_chat_message_attachment_message_id", table_name="chat_message_attachment"
    )
    op.drop_table("chat_message_attachment")
