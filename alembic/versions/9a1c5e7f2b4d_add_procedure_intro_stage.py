"""add procedure_intro journey stage

Revision ID: 9a1c5e7f2b4d
Revises: 7c4e9a2f1b6d
Create Date: 2026-08-21 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9a1c5e7f2b4d'
down_revision: Union[str, Sequence[str], None] = '7c4e9a2f1b6d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PG 12+ allows ALTER TYPE ... ADD VALUE inside a normal
    # transaction - the only restriction is that the new value cannot
    # be USED (e.g. in an INSERT/UPDATE) within that same transaction.
    # This migration deliberately does NOT insert the journey_stages
    # row for PROCEDURE_INTRO - that's left entirely to
    # scripts/seed_lookup_data.py, which runs as its own separate
    # process/connection/transaction *after* this migration has
    # committed, so it can safely use the new enum value with zero
    # risk of the "unsafe use of new value" error.
    op.execute(
        "ALTER TYPE journeystagecode ADD VALUE IF NOT EXISTS 'PROCEDURE_INTRO' BEFORE 'BEFORE_PROCEDURE'"
    )

    # display_order=4 was vacated when PROCEDURE was retired (migration
    # 7c4e9a2f1b6d), so BEFORE_PROCEDURE can move into it and
    # PROCEDURE_INTRO takes the freed-up slot 3 once seeded. This
    # UPDATE only touches existing rows/values, so it's safe here.
    op.execute("UPDATE journey_stages SET display_order = 4 WHERE code = 'BEFORE_PROCEDURE'")


def downgrade() -> None:
    # Best-effort only: moves any patients currently on PROCEDURE_INTRO
    # back to BEFORE_PROCEDURE, and removes the journey_stages row if
    # scripts/seed_lookup_data.py already created it. Does NOT delete
    # education_sections / quiz_questions already authored under this
    # stage (they'd need manual review first) and does NOT remove
    # 'PROCEDURE_INTRO' from the Postgres enum type - Postgres does not
    # support dropping enum values.
    op.execute("""
        UPDATE patient_journey_profiles
        SET current_stage = 'BEFORE_PROCEDURE'
        WHERE current_stage = 'PROCEDURE_INTRO'
    """)
    op.execute("DELETE FROM journey_stages WHERE code = 'PROCEDURE_INTRO'")
    op.execute("UPDATE journey_stages SET display_order = 3 WHERE code = 'BEFORE_PROCEDURE'")