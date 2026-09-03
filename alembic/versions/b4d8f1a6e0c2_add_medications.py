"""add medications

Revision ID: b4d8f1a6e0c2
Revises: e5f8a2c1b9d3
Create Date: 2026-09-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b4d8f1a6e0c2'
down_revision: Union[str, Sequence[str], None] = 'e5f8a2c1b9d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'medications',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('department_type_id', sa.UUID(), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('body_richtext', sa.Text(), nullable=True),
        sa.Column('image_url', sa.String(length=1024), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['department_type_id'], ['standard_department_types.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_medications_department_type_id'), 'medications', ['department_type_id'], unique=False)
    op.create_index(op.f('ix_medications_slug'), 'medications', ['slug'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_medications_slug'), table_name='medications')
    op.drop_index(op.f('ix_medications_department_type_id'), table_name='medications')
    op.drop_table('medications')