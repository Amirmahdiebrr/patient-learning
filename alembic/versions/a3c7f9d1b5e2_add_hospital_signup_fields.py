"""add hospital signup contact fields

Revision ID: a3c7f9d1b5e2
Revises: f4b7c1a9d2e8
Create Date: 2026-08-14 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a3c7f9d1b5e2'
down_revision: Union[str, Sequence[str], None] = 'f4b7c1a9d2e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('hospitals', sa.Column('address', sa.String(length=500), nullable=True))
    op.add_column('hospitals', sa.Column('phone_number', sa.String(length=20), nullable=True))
    op.add_column('hospitals', sa.Column('responsible_phone', sa.String(length=20), nullable=True))
    op.add_column('hospitals', sa.Column('responsible_national_id', sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column('hospitals', 'responsible_national_id')
    op.drop_column('hospitals', 'responsible_phone')
    op.drop_column('hospitals', 'phone_number')
    op.drop_column('hospitals', 'address')