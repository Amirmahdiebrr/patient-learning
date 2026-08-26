"""add hospital_welcome_acknowledged_at to patient_access_profiles

Revision ID: c3d7f2a9e5b1
Revises: a9c2e5f8b1d4
Create Date: 2026-08-26 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3d7f2a9e5b1'
down_revision: Union[str, Sequence[str], None] = 'a9c2e5f8b1d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('patient_access_profiles', sa.Column('hospital_welcome_acknowledged_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('patient_access_profiles', 'hospital_welcome_acknowledged_at')