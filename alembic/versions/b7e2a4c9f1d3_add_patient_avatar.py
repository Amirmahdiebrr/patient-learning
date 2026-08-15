"""add avatar_url to patient_registrations

Revision ID: b7e2a4c9f1d3
Revises: a3c7f9d1b5e2
Create Date: 2026-08-14 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7e2a4c9f1d3'
down_revision: Union[str, Sequence[str], None] = 'a3c7f9d1b5e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('patient_registrations', sa.Column('avatar_url', sa.String(length=1024), nullable=True))


def downgrade() -> None:
    op.drop_column('patient_registrations', 'avatar_url')