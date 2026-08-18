"""add approved_at to nurse users

Revision ID: e3b6d9f2a5c8
Revises: d2a5c8e1f4b7
Create Date: 2026-08-18 15:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e3b6d9f2a5c8'
down_revision: Union[str, Sequence[str], None] = 'd2a5c8e1f4b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('nurse_users', sa.Column('approved_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('nurse_users', 'approved_at')