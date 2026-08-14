# alembic/versions/f4b7c1a9d2e8_add_patient_self_service_auth.py
"""add patient self-service auth (password) and direct hospital/department on access profile

Revision ID: f4b7c1a9d2e8
Revises: e1a2b3c4d5f6
Create Date: 2026-08-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f4b7c1a9d2e8'
down_revision: Union[str, Sequence[str], None] = 'e1a2b3c4d5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('patient_registrations', sa.Column('password_hash', sa.String(length=255), nullable=True))

    op.alter_column('patient_access_profiles', 'qr_access_point_id', existing_type=sa.UUID(), nullable=True)
    op.add_column('patient_access_profiles', sa.Column('hospital_id', sa.UUID(), nullable=True))
    op.add_column('patient_access_profiles', sa.Column('department_id', sa.UUID(), nullable=True))
    op.create_index(op.f('ix_patient_access_profiles_hospital_id'), 'patient_access_profiles', ['hospital_id'], unique=False)
    op.create_index(op.f('ix_patient_access_profiles_department_id'), 'patient_access_profiles', ['department_id'], unique=False)
    op.create_foreign_key('fk_patient_access_profiles_hospital_id', 'patient_access_profiles', 'hospitals', ['hospital_id'], ['id'])
    op.create_foreign_key('fk_patient_access_profiles_department_id', 'patient_access_profiles', 'departments', ['department_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint('fk_patient_access_profiles_department_id', 'patient_access_profiles', type_='foreignkey')
    op.drop_constraint('fk_patient_access_profiles_hospital_id', 'patient_access_profiles', type_='foreignkey')
    op.drop_index(op.f('ix_patient_access_profiles_department_id'), table_name='patient_access_profiles')
    op.drop_index(op.f('ix_patient_access_profiles_hospital_id'), table_name='patient_access_profiles')
    op.drop_column('patient_access_profiles', 'department_id')
    op.drop_column('patient_access_profiles', 'hospital_id')
    op.alter_column('patient_access_profiles', 'qr_access_point_id', existing_type=sa.UUID(), nullable=False)

    op.drop_column('patient_registrations', 'password_hash')