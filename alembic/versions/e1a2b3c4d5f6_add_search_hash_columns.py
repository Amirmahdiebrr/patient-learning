"""add blind-index hash columns for encrypted patient fields

Revision ID: e1a2b3c4d5f6
Revises: 3d8f1a5c7b2e
Create Date: 2026-08-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e1a2b3c4d5f6'
down_revision: Union[str, Sequence[str], None] = '3d8f1a5c7b2e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('patient_registrations', sa.Column('national_id_hash', sa.String(length=64), nullable=True))
    op.add_column('patient_registrations', sa.Column('phone_number_hash', sa.String(length=64), nullable=True))
    op.create_index(op.f('ix_patient_registrations_national_id_hash'), 'patient_registrations', ['national_id_hash'], unique=False)
    op.create_index(op.f('ix_patient_registrations_phone_number_hash'), 'patient_registrations', ['phone_number_hash'], unique=False)

    # Best-effort backfill for existing rows. Skipped (rows keep NULL
    # hashes until the patient re-saves) if either key is unset at
    # migration time - this must never fail the migration itself.
    from app.core.config import settings
    if not settings.ENCRYPTION_KEY or not settings.SEARCH_HASH_KEY:
        return

    from cryptography.fernet import Fernet, InvalidToken
    from app.core.encryption import blind_index

    fernet = Fernet(settings.ENCRYPTION_KEY.encode())
    conn = op.get_bind()
    rows = conn.execute(sa.text(
        "SELECT id, national_id, phone_number FROM patient_registrations"
    )).fetchall()

    for row in rows:
        try:
            national_id = fernet.decrypt(row.national_id.encode()).decode()
            phone_number = fernet.decrypt(row.phone_number.encode()).decode()
        except (InvalidToken, AttributeError):
            continue

        conn.execute(
            sa.text(
                "UPDATE patient_registrations SET national_id_hash = :nid, phone_number_hash = :ph WHERE id = :id"
            ),
            {"nid": blind_index(national_id), "ph": blind_index(phone_number), "id": row.id},
        )


def downgrade() -> None:
    op.drop_index(op.f('ix_patient_registrations_phone_number_hash'), table_name='patient_registrations')
    op.drop_index(op.f('ix_patient_registrations_national_id_hash'), table_name='patient_registrations')
    op.drop_column('patient_registrations', 'phone_number_hash')
    op.drop_column('patient_registrations', 'national_id_hash')