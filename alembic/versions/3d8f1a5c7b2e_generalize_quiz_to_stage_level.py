"""generalize quiz to stage level + flexible options + images

Revision ID: 3d8f1a5c7b2e
Revises: 6c4f2b8e9a1d
Create Date: 2026-08-09 08:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '3d8f1a5c7b2e'
down_revision: Union[str, Sequence[str], None] = '6c4f2b8e9a1d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('quiz_questions', 'lesson_id', existing_type=sa.UUID(), nullable=True)

    op.add_column('quiz_questions', sa.Column('journey_stage_id', sa.UUID(), nullable=True))
    op.add_column('quiz_questions', sa.Column('department_type_id', sa.UUID(), nullable=True))
    op.add_column('quiz_questions', sa.Column('question_image_url', sa.String(length=1024), nullable=True))

    op.create_index(op.f('ix_quiz_questions_journey_stage_id'), 'quiz_questions', ['journey_stage_id'], unique=False)
    op.create_index(op.f('ix_quiz_questions_department_type_id'), 'quiz_questions', ['department_type_id'], unique=False)
    op.create_foreign_key('fk_quiz_questions_journey_stage_id', 'quiz_questions', 'journey_stages', ['journey_stage_id'], ['id'])
    op.create_foreign_key('fk_quiz_questions_department_type_id', 'quiz_questions', 'standard_department_types', ['department_type_id'], ['id'])

    op.add_column('quiz_options', sa.Column('option_image_url', sa.String(length=1024), nullable=True))


def downgrade() -> None:
    op.drop_column('quiz_options', 'option_image_url')

    op.drop_constraint('fk_quiz_questions_department_type_id', 'quiz_questions', type_='foreignkey')
    op.drop_constraint('fk_quiz_questions_journey_stage_id', 'quiz_questions', type_='foreignkey')
    op.drop_index(op.f('ix_quiz_questions_department_type_id'), table_name='quiz_questions')
    op.drop_index(op.f('ix_quiz_questions_journey_stage_id'), table_name='quiz_questions')
    op.drop_column('quiz_questions', 'question_image_url')
    op.drop_column('quiz_questions', 'department_type_id')
    op.drop_column('quiz_questions', 'journey_stage_id')

    op.alter_column('quiz_questions', 'lesson_id', existing_type=sa.UUID(), nullable=False)