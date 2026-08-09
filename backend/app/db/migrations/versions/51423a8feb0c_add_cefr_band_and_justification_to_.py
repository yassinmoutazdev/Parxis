"""Add CEFR band and justification to WritingEvaluation

Revision ID: 51423a8feb0c
Revises: 6_restrict_quiz_mode
Create Date: 2026-08-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '51423a8feb0c'
down_revision: Union[str, None] = '6_restrict_quiz_mode'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add CEFR band and justification columns to writing_evaluation
    op.add_column(
        'writing_evaluation',
        sa.Column('cefr_band', sa.String(), nullable=True, index=True)
    )
    op.add_column(
        'writing_evaluation',
        sa.Column('cefr_justification', sa.String(), nullable=True)
    )


def downgrade() -> None:
    # Remove the columns
    op.drop_column('writing_evaluation', 'cefr_justification')
    op.drop_column('writing_evaluation', 'cefr_band')