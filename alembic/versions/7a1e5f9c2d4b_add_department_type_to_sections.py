"""add department_type_id to education_sections

Revision ID: 7a1e5f9c2d4b
Revises: 2f8a6c1d9b3e
Create Date: 2026-07-31 05:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7a1e5f9c2d4b'
down_revision: Union[str, Sequence[str], None] = '2f8a6c1d9b3e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('education_sections', sa.Column('department_type_id', sa.UUID(), nullable=True))
    op.create_index(
        op.f('ix_education_sections_department_type_id'),
        'education_sections', ['department_type_id'], unique=False,
    )
    op.create_foreign_key(
        'fk_education_sections_department_type_id', 'education_sections',
        'standard_department_types', ['department_type_id'], ['id'],
    )


def downgrade() -> None:
    op.drop_constraint('fk_education_sections_department_type_id', 'education_sections', type_='foreignkey')
    op.drop_index(op.f('ix_education_sections_department_type_id'), table_name='education_sections')
    op.drop_column('education_sections', 'department_type_id')