"""add nurse users

Revision ID: c8f3e7a2b4d1
Revises: b7e2a4c9f1d3
Create Date: 2026-08-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c8f3e7a2b4d1'
down_revision: Union[str, Sequence[str], None] = 'b7e2a4c9f1d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'nurse_users',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('hospital_id', sa.UUID(), nullable=False),
        sa.Column('department_id', sa.UUID(), nullable=True),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['hospital_id'], ['hospitals.id']),
        sa.ForeignKeyConstraint(['department_id'], ['departments.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_nurse_users_hospital_id'), 'nurse_users', ['hospital_id'], unique=False)
    op.create_index(op.f('ix_nurse_users_department_id'), 'nurse_users', ['department_id'], unique=False)
    op.create_index(op.f('ix_nurse_users_email'), 'nurse_users', ['email'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_nurse_users_email'), table_name='nurse_users')
    op.drop_index(op.f('ix_nurse_users_department_id'), table_name='nurse_users')
    op.drop_index(op.f('ix_nurse_users_hospital_id'), table_name='nurse_users')
    op.drop_table('nurse_users')