"""add ghost patient profiles for admin QA browsing

Revision ID: a9c2e5f8b1d4
Revises: f1a4c7e9b2d6
Create Date: 2026-08-24 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a9c2e5f8b1d4'
down_revision: Union[str, Sequence[str], None] = 'f1a4c7e9b2d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('patient_access_profiles', sa.Column('is_ghost', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('patient_access_profiles', sa.Column('ghost_created_by_admin_id', sa.UUID(), nullable=True))
    op.add_column('patient_access_profiles', sa.Column('ghost_label', sa.String(length=255), nullable=True))

    op.create_index(op.f('ix_patient_access_profiles_is_ghost'), 'patient_access_profiles', ['is_ghost'], unique=False)
    op.create_foreign_key(
        'fk_patient_access_profiles_ghost_created_by_admin_id',
        'patient_access_profiles', 'admin_users', ['ghost_created_by_admin_id'], ['id'],
    )


def downgrade() -> None:
    op.drop_constraint('fk_patient_access_profiles_ghost_created_by_admin_id', 'patient_access_profiles', type_='foreignkey')
    op.drop_index(op.f('ix_patient_access_profiles_is_ghost'), table_name='patient_access_profiles')
    op.drop_column('patient_access_profiles', 'ghost_label')
    op.drop_column('patient_access_profiles', 'ghost_created_by_admin_id')
    op.drop_column('patient_access_profiles', 'is_ghost')