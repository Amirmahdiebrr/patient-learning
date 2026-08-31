# alembic/versions/e5f8a2c1b9d3_add_general_welcome_ack.py
"""add general_welcome_acknowledged_at to patient_access_profiles

Revision ID: e5f8a2c1b9d3
Revises: c3d7f2a9e5b1
Create Date: 2026-08-27 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e5f8a2c1b9d3'
down_revision: Union[str, Sequence[str], None] = 'c3d7f2a9e5b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('patient_access_profiles', sa.Column('general_welcome_acknowledged_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('patient_access_profiles', 'general_welcome_acknowledged_at')