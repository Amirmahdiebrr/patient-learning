"""merge general_education and department_intro into admission

Revision ID: 6c4f2b8e9a1d
Revises: 2a7c9f4b1d6e
Create Date: 2026-08-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '6c4f2b8e9a1d'
down_revision: Union[str, Sequence[str], None] = '2a7c9f4b1d6e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Move any content/patients from general_education & department_intro to admission
    op.execute("""
        UPDATE education_sections
        SET journey_stage_id = (SELECT id FROM journey_stages WHERE code = 'ADMISSION')
        WHERE journey_stage_id IN (
            SELECT id FROM journey_stages WHERE code IN ('GENERAL_EDUCATION', 'DEPARTMENT_INTRO')
        )
    """)

    op.execute("""
        UPDATE patient_journey_profiles
        SET current_stage = 'ADMISSION'
        WHERE current_stage IN ('GENERAL_EDUCATION', 'DEPARTMENT_INTRO')
    """)

    op.execute("""
        UPDATE journey_stages
        SET name = 'پذیرش در بخش'
        WHERE code = 'ADMISSION'
    """)

    op.execute("""
        DELETE FROM journey_stages
        WHERE code IN ('GENERAL_EDUCATION', 'DEPARTMENT_INTRO')
    """)


def downgrade() -> None:
    # Best-effort only: recreates the two stage rows but cannot restore
    # which sections/patients originally belonged to them (that
    # information was merged into ADMISSION and is not tracked).
    op.execute("""
        INSERT INTO journey_stages (id, code, name, display_order)
        VALUES
            (gen_random_uuid(), 'GENERAL_EDUCATION', 'آموزش عمومی بیمارستان', 2),
            (gen_random_uuid(), 'DEPARTMENT_INTRO', 'معرفی بخش', 3)
        ON CONFLICT DO NOTHING
    """)

    op.execute("""
        UPDATE journey_stages
        SET name = 'بستری / پذیرش'
        WHERE code = 'ADMISSION'
    """)