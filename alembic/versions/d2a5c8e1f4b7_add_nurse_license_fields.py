"""add nurse license fields

Revision ID: d2a5c8e1f4b7
Revises: c8f3e7a2b4d1
Create Date: 2026-08-18 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd2a5c8e1f4b7'
down_revision: Union[str, Sequence[str], None] = 'c8f3e7a2b4d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('nurse_users', sa.Column('national_id', sa.String(length=20), nullable=False, server_default=''))
    op.add_column('nurse_users', sa.Column('nursing_license_number', sa.String(length=50), nullable=False, server_default=''))
    op.alter_column('nurse_users', 'is_active', server_default='false')
    op.create_index(op.f('ix_nurse_users_nursing_license_number'), 'nurse_users', ['nursing_license_number'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_nurse_users_nursing_license_number'), table_name='nurse_users')
    op.alter_column('nurse_users', 'is_active', server_default='true')
    op.drop_column('nurse_users', 'nursing_license_number')
    op.drop_column('nurse_users', 'national_id')