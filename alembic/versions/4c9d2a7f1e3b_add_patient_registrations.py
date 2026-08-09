"""add patient registrations

Revision ID: 4c9d2a7f1e3b
Revises: 7a1e5f9c2d4b
Create Date: 2026-07-31 06:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '4c9d2a7f1e3b'
down_revision: Union[str, Sequence[str], None] = '7a1e5f9c2d4b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'patient_registrations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('patient_access_profile_id', sa.UUID(), nullable=False),
        sa.Column('first_name', sa.String(length=255), nullable=False),
        sa.Column('last_name', sa.String(length=255), nullable=False),
        sa.Column('national_id', sa.String(length=20), nullable=False),
        sa.Column('phone_number', sa.String(length=20), nullable=False),
        sa.Column('insurance_code', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['patient_access_profile_id'], ['patient_access_profiles.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_patient_registrations_patient_access_profile_id'),
        'patient_registrations', ['patient_access_profile_id'], unique=True,
    )
    op.create_index(
        op.f('ix_patient_registrations_national_id'),
        'patient_registrations', ['national_id'], unique=False,
    )
    op.create_index(
        op.f('ix_patient_registrations_phone_number'),
        'patient_registrations', ['phone_number'], unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_patient_registrations_phone_number'), table_name='patient_registrations')
    op.drop_index(op.f('ix_patient_registrations_national_id'), table_name='patient_registrations')
    op.drop_index(op.f('ix_patient_registrations_patient_access_profile_id'), table_name='patient_registrations')
    op.drop_table('patient_registrations')