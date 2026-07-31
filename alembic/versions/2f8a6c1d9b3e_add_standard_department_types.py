"""add standard department types

Revision ID: 2f8a6c1d9b3e
Revises: 197414cd40e5
Create Date: 2026-07-31 04:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '2f8a6c1d9b3e'
down_revision: Union[str, Sequence[str], None] = '197414cd40e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'standard_department_types',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('macro_category', sa.Enum(
            'SURGICAL', 'MEDICAL', 'CRITICAL_CARE', 'OBSTETRICS_GYNECOLOGY',
            'PEDIATRICS', 'OUTPATIENT_PROCEDURES',
            name='departmentmacrocategory',
        ), nullable=False),
        sa.Column('code', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('display_order', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_standard_department_types_macro_category'), 'standard_department_types', ['macro_category'], unique=False)
    op.create_index(op.f('ix_standard_department_types_code'), 'standard_department_types', ['code'], unique=True)

    op.add_column('departments', sa.Column('department_type_id', sa.UUID(), nullable=True))
    op.create_index(op.f('ix_departments_department_type_id'), 'departments', ['department_type_id'], unique=False)
    op.create_foreign_key(
        'fk_departments_department_type_id', 'departments', 'standard_department_types',
        ['department_type_id'], ['id'],
    )


def downgrade() -> None:
    op.drop_constraint('fk_departments_department_type_id', 'departments', type_='foreignkey')
    op.drop_index(op.f('ix_departments_department_type_id'), table_name='departments')
    op.drop_column('departments', 'department_type_id')

    op.drop_index(op.f('ix_standard_department_types_code'), table_name='standard_department_types')
    op.drop_index(op.f('ix_standard_department_types_macro_category'), table_name='standard_department_types')
    op.drop_table('standard_department_types')