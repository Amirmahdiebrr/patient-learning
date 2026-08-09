"""add lesson hospital overrides and followup tasks

Revision ID: 2a7c9f4b1d6e
Revises: 5f3c8a2d7e1b
Create Date: 2026-08-04 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '2a7c9f4b1d6e'
down_revision: Union[str, Sequence[str], None] = '5f3c8a2d7e1b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    lesson_override_level = postgresql.ENUM('GLOBAL', 'HOSPITAL', name='lessonoverridelevel')
    lesson_override_level.create(op.get_bind(), checkfirst=True)

    followup_channel = postgresql.ENUM('SMS', 'CALL', 'NOTIFICATION', name='followupchannel')
    followup_channel.create(op.get_bind(), checkfirst=True)

    followup_status = postgresql.ENUM('PENDING', 'SENT', 'FAILED', 'CANCELLED', name='followupstatus')
    followup_status.create(op.get_bind(), checkfirst=True)

    op.add_column('lessons', sa.Column(
        'override_level',
        postgresql.ENUM('GLOBAL', 'HOSPITAL', name='lessonoverridelevel', create_type=False),
        nullable=False, server_default='GLOBAL',
    ))
    op.add_column('lessons', sa.Column('parent_lesson_id', sa.UUID(), nullable=True))
    op.add_column('lessons', sa.Column('hospital_id', sa.UUID(), nullable=True))
    op.create_index(op.f('ix_lessons_parent_lesson_id'), 'lessons', ['parent_lesson_id'], unique=False)
    op.create_index(op.f('ix_lessons_hospital_id'), 'lessons', ['hospital_id'], unique=False)
    op.create_foreign_key('fk_lessons_parent_lesson_id', 'lessons', 'lessons', ['parent_lesson_id'], ['id'])
    op.create_foreign_key('fk_lessons_hospital_id', 'lessons', 'hospitals', ['hospital_id'], ['id'])

    op.create_table(
        'followup_tasks',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('patient_access_profile_id', sa.UUID(), nullable=False),
        sa.Column('hospital_id', sa.UUID(), nullable=False),
        sa.Column('channel', postgresql.ENUM('SMS', 'CALL', 'NOTIFICATION', name='followupchannel', create_type=False), nullable=False),
        sa.Column('status', postgresql.ENUM('PENDING', 'SENT', 'FAILED', 'CANCELLED', name='followupstatus', create_type=False), nullable=False),
        sa.Column('scheduled_at', sa.DateTime(), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('provider_name', sa.String(length=100), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['patient_access_profile_id'], ['patient_access_profiles.id']),
        sa.ForeignKeyConstraint(['hospital_id'], ['hospitals.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_followup_tasks_patient_access_profile_id'), 'followup_tasks', ['patient_access_profile_id'], unique=False)
    op.create_index(op.f('ix_followup_tasks_hospital_id'), 'followup_tasks', ['hospital_id'], unique=False)
    op.create_index(op.f('ix_followup_tasks_status'), 'followup_tasks', ['status'], unique=False)
    op.create_index(op.f('ix_followup_tasks_scheduled_at'), 'followup_tasks', ['scheduled_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_followup_tasks_scheduled_at'), table_name='followup_tasks')
    op.drop_index(op.f('ix_followup_tasks_status'), table_name='followup_tasks')
    op.drop_index(op.f('ix_followup_tasks_hospital_id'), table_name='followup_tasks')
    op.drop_index(op.f('ix_followup_tasks_patient_access_profile_id'), table_name='followup_tasks')
    op.drop_table('followup_tasks')

    op.drop_constraint('fk_lessons_hospital_id', 'lessons', type_='foreignkey')
    op.drop_constraint('fk_lessons_parent_lesson_id', 'lessons', type_='foreignkey')
    op.drop_index(op.f('ix_lessons_hospital_id'), table_name='lessons')
    op.drop_index(op.f('ix_lessons_parent_lesson_id'), table_name='lessons')
    op.drop_column('lessons', 'hospital_id')
    op.drop_column('lessons', 'parent_lesson_id')
    op.drop_column('lessons', 'override_level')

    postgresql.ENUM(name='followupstatus').drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name='followupchannel').drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name='lessonoverridelevel').drop(op.get_bind(), checkfirst=True)