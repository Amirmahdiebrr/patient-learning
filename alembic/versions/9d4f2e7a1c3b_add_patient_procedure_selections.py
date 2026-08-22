"""add patient procedure selections (multi-procedure support)

Revision ID: 9d4f2e7a1c3b
Revises: 7c4e9a2f1b6d
Create Date: 2026-08-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9d4f2e7a1c3b'
down_revision: Union[str, Sequence[str], None] = '7c4e9a2f1b6d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'patient_procedure_selections',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('patient_access_profile_id', sa.UUID(), nullable=False),
        sa.Column('procedure_id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['patient_access_profile_id'], ['patient_access_profiles.id']),
        sa.ForeignKeyConstraint(['procedure_id'], ['procedures.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('patient_access_profile_id', 'procedure_id', name='uq_patient_procedure_selection'),
    )
    op.create_index(
        op.f('ix_patient_procedure_selections_patient_access_profile_id'),
        'patient_procedure_selections', ['patient_access_profile_id'], unique=False,
    )
    op.create_index(
        op.f('ix_patient_procedure_selections_procedure_id'),
        'patient_procedure_selections', ['procedure_id'], unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_patient_procedure_selections_procedure_id'), table_name='patient_procedure_selections')
    op.drop_index(op.f('ix_patient_procedure_selections_patient_access_profile_id'), table_name='patient_procedure_selections')
    op.drop_table('patient_procedure_selections')