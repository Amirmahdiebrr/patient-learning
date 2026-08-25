"""merge home_care, follow_up and long_term_monitoring into "پیگیری و مراقبت در منزل"

Revision ID: f1a4c7e9b2d6
Revises: 61de18543736
Create Date: 2026-08-23 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f1a4c7e9b2d6'
down_revision: Union[str, Sequence[str], None] = '61de18543736'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Move any content/patients from FOLLOW_UP & LONG_TERM_MONITORING to HOME_CARE
    op.execute("""
        UPDATE education_sections
        SET journey_stage_id = (SELECT id FROM journey_stages WHERE code = 'HOME_CARE')
        WHERE journey_stage_id IN (
            SELECT id FROM journey_stages WHERE code IN ('FOLLOW_UP', 'LONG_TERM_MONITORING')
        )
    """)

    op.execute("""
        UPDATE quiz_questions
        SET journey_stage_id = (SELECT id FROM journey_stages WHERE code = 'HOME_CARE')
        WHERE journey_stage_id IN (
            SELECT id FROM journey_stages WHERE code IN ('FOLLOW_UP', 'LONG_TERM_MONITORING')
        )
    """)

    op.execute("""
        UPDATE patient_journey_profiles
        SET current_stage = 'HOME_CARE'
        WHERE current_stage IN ('FOLLOW_UP', 'LONG_TERM_MONITORING')
    """)

    op.execute("""
        UPDATE journey_stages
        SET name = 'پیگیری و مراقبت در منزل'
        WHERE code = 'HOME_CARE'
    """)

    op.execute("""
        DELETE FROM journey_stages
        WHERE code IN ('FOLLOW_UP', 'LONG_TERM_MONITORING')
    """)


def downgrade() -> None:
    # Best-effort only: recreates the two stage rows but cannot restore
    # which sections/patients originally belonged to each of them (that
    # information was merged into HOME_CARE and is not tracked).
    op.execute("""
        INSERT INTO journey_stages (id, code, name, display_order)
        VALUES
            (gen_random_uuid(), 'FOLLOW_UP', 'پیگیری', 9),
            (gen_random_uuid(), 'LONG_TERM_MONITORING', 'پایش بلندمدت', 10)
        ON CONFLICT DO NOTHING
    """)

    op.execute("""
        UPDATE journey_stages
        SET name = 'مراقبت در منزل'
        WHERE code = 'HOME_CARE'
    """)