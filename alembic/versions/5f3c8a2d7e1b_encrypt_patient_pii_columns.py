"""widen patient_registrations pii columns for encrypted values

Revision ID: 5f3c8a2d7e1b
Revises: 8b2e4f7a1c9d
Create Date: 2026-08-04 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '5f3c8a2d7e1b'
down_revision: Union[str, Sequence[str], None] = '8b2e4f7a1c9d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('patient_registrations', 'national_id',
                     existing_type=sa.String(length=20), type_=sa.String(length=255))
    op.alter_column('patient_registrations', 'phone_number',
                     existing_type=sa.String(length=20), type_=sa.String(length=255))
    op.alter_column('patient_registrations', 'insurance_code',
                     existing_type=sa.String(length=100), type_=sa.String(length=255))


def downgrade() -> None:
    op.alter_column('patient_registrations', 'insurance_code',
                     existing_type=sa.String(length=255), type_=sa.String(length=100))
    op.alter_column('patient_registrations', 'phone_number',
                     existing_type=sa.String(length=255), type_=sa.String(length=20))
    op.alter_column('patient_registrations', 'national_id',
                     existing_type=sa.String(length=255), type_=sa.String(length=20))