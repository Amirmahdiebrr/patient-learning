# alembic/versions/7c4e9a2f1b6d_add_procedures_and_retire_procedure_stage.py
"""add procedures catalog, department_type is_active, retire PROCEDURE stage

Revision ID: 7c4e9a2f1b6d
Revises: e3b6d9f2a5c8
Create Date: 2026-08-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7c4e9a2f1b6d'
down_revision: Union[str, Sequence[str], None] = 'e3b6d9f2a5c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- standard_department_types.is_active ----
    op.add_column('standard_department_types', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'))
    op.execute("""
        UPDATE standard_department_types
        SET is_active = false
        WHERE code IN ('nicu_parent_education', 'picu_parent_education')
    """)

    # ---- procedures ----
    op.create_table(
        'procedures',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('department_type_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['department_type_id'], ['standard_department_types.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_procedures_department_type_id'), 'procedures', ['department_type_id'], unique=False)
    op.create_index(op.f('ix_procedures_slug'), 'procedures', ['slug'], unique=False)

    # ---- education_sections.procedure_id ----
    op.add_column('education_sections', sa.Column('procedure_id', sa.UUID(), nullable=True))
    op.create_index(op.f('ix_education_sections_procedure_id'), 'education_sections', ['procedure_id'], unique=False)
    op.create_foreign_key('fk_education_sections_procedure_id', 'education_sections', 'procedures', ['procedure_id'], ['id'])

    # ---- quiz_questions.procedure_id ----
    op.add_column('quiz_questions', sa.Column('procedure_id', sa.UUID(), nullable=True))
    op.create_index(op.f('ix_quiz_questions_procedure_id'), 'quiz_questions', ['procedure_id'], unique=False)
    op.create_foreign_key('fk_quiz_questions_procedure_id', 'quiz_questions', 'procedures', ['procedure_id'], ['id'])

    # ---- patient_journey_profiles.procedure_id ----
    op.add_column('patient_journey_profiles', sa.Column('procedure_id', sa.UUID(), nullable=True))
    op.create_index(op.f('ix_patient_journey_profiles_procedure_id'), 'patient_journey_profiles', ['procedure_id'], unique=False)
    op.create_foreign_key('fk_patient_journey_profiles_procedure_id', 'patient_journey_profiles', 'procedures', ['procedure_id'], ['id'])

    # ---- retire "حین عمل" (PROCEDURE) stage -> merge into BEFORE_PROCEDURE ----
    op.execute("""
        UPDATE education_sections
        SET journey_stage_id = (SELECT id FROM journey_stages WHERE code = 'BEFORE_PROCEDURE')
        WHERE journey_stage_id IN (SELECT id FROM journey_stages WHERE code = 'PROCEDURE')
    """)
    op.execute("""
        UPDATE quiz_questions
        SET journey_stage_id = (SELECT id FROM journey_stages WHERE code = 'BEFORE_PROCEDURE')
        WHERE journey_stage_id IN (SELECT id FROM journey_stages WHERE code = 'PROCEDURE')
    """)
    op.execute("""
        UPDATE patient_journey_profiles
        SET current_stage = 'BEFORE_PROCEDURE'
        WHERE current_stage = 'PROCEDURE'
    """)
    op.execute("DELETE FROM journey_stages WHERE code = 'PROCEDURE'")


def downgrade() -> None:
    op.execute("""
        INSERT INTO journey_stages (id, code, name, display_order)
        VALUES (gen_random_uuid(), 'PROCEDURE', 'حین عمل', 4)
        ON CONFLICT DO NOTHING
    """)

    op.drop_constraint('fk_patient_journey_profiles_procedure_id', 'patient_journey_profiles', type_='foreignkey')
    op.drop_index(op.f('ix_patient_journey_profiles_procedure_id'), table_name='patient_journey_profiles')
    op.drop_column('patient_journey_profiles', 'procedure_id')

    op.drop_constraint('fk_quiz_questions_procedure_id', 'quiz_questions', type_='foreignkey')
    op.drop_index(op.f('ix_quiz_questions_procedure_id'), table_name='quiz_questions')
    op.drop_column('quiz_questions', 'procedure_id')

    op.drop_constraint('fk_education_sections_procedure_id', 'education_sections', type_='foreignkey')
    op.drop_index(op.f('ix_education_sections_procedure_id'), table_name='education_sections')
    op.drop_column('education_sections', 'procedure_id')

    op.drop_index(op.f('ix_procedures_slug'), table_name='procedures')
    op.drop_index(op.f('ix_procedures_department_type_id'), table_name='procedures')
    op.drop_table('procedures')

    op.execute("""
        UPDATE standard_department_types
        SET is_active = true
        WHERE code IN ('nicu_parent_education', 'picu_parent_education')
    """)
    op.drop_column('standard_department_types', 'is_active')