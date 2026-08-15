"""Remove approval queue (Part H)

Approval service removed entirely - screening is now automatic (duplicate
check + one self-correction retry, resolved by source: vault items still
unresolved after retry are dropped silently, chat items trigger a
clarifying question in the same conversation turn instead of a queue).

- Drops approval_queue table
- Drops source_approval_id from learning_item and learning_correction
  (was a required FK into approval_queue; provenance is already covered
  by source_note_id / source_writing_evaluation_id)
- Adds note.source ('vault' | 'chat') and note.content (raw text for
  chat-sourced notes, which have no file on disk)
- note.vault_path becomes nullable (chat-sourced notes have none)

Revision ID: 7_remove_approval_queue
Revises: 51423a8feb0c
Create Date: 2026-08-13

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "7_remove_approval_queue"
down_revision: str | None = "51423a8feb0c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- note: add source/content, relax vault_path ---
    with op.batch_alter_table("note") as batch_op:
        batch_op.add_column(
            sa.Column("source", sa.String(), nullable=False, server_default="vault")
        )
        batch_op.add_column(sa.Column("content", sa.Text(), nullable=True))
        batch_op.alter_column("vault_path", existing_type=sa.String(), nullable=True)

    # --- learning_item: drop source_approval_id (and its index) ---
    with op.batch_alter_table("learning_item") as batch_op:
        batch_op.drop_index("ix_learning_item_source_approval_id")
        batch_op.drop_column("source_approval_id")

    # --- learning_correction: drop source_approval_id (and its index) ---
    with op.batch_alter_table("learning_correction") as batch_op:
        batch_op.drop_index("ix_learning_correction_source_approval_id")
        batch_op.drop_column("source_approval_id")

    # --- approval_queue: drop entirely ---
    op.drop_table("approval_queue")


def downgrade() -> None:
    # Recreate approval_queue with its original shape (from the initial
    # migration) so downgrade doesn't lose the table structure, though any
    # rows created after upgrade() are gone - this is a lossy downgrade.
    op.create_table(
        "approval_queue",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("item_type", sa.String(), nullable=False),
        sa.Column("extracted_text", sa.String(), nullable=False),
        sa.Column("explanation", sa.String(), nullable=True),
        sa.Column("example_sentence", sa.String(), nullable=True),
        sa.Column("source_context", sa.String(), nullable=True),
        sa.Column("possible_duplicate_of", sa.Integer(), nullable=True),
        sa.Column("reviewed_payload", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
    )

    with op.batch_alter_table("learning_correction") as batch_op:
        batch_op.add_column(
            sa.Column("source_approval_id", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.create_index(
            "ix_learning_correction_source_approval_id", ["source_approval_id"]
        )

    with op.batch_alter_table("learning_item") as batch_op:
        batch_op.add_column(
            sa.Column("source_approval_id", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.create_index("ix_learning_item_source_approval_id", ["source_approval_id"])

    with op.batch_alter_table("note") as batch_op:
        batch_op.alter_column("vault_path", existing_type=sa.String(), nullable=False)
        batch_op.drop_column("content")
        batch_op.drop_column("source")
