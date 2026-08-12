"""add patient referrals, hospital api keys, national_id_hash

Revision ID: 9f2e5b8c1a4d
Revises: 3d8f1a5c7b2e
Create Date: 2026-08-10 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '9f2e5b8c1a4d'
down_revision: Union[str, Sequence[str], None] = '3d8f1a5c7b2e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    referral_source = postgresql.ENUM('MANUAL', 'API', name='referralsource')
    referral_source.create(op.get_bind(), checkfirst=True)

    referral_status = postgresql.ENUM('RECEIVED', 'MATCHED', 'REVIEWED', name='referralstatus')
    referral_status.create(op.get_bind(), checkfirst=True)

    # ---- national_id_hash on patient_registrations ----
    op.add_column('patient_registrations', sa.Column('national_id_hash', sa.String(length=64), nullable=True))
    op.create_index(op.f('ix_patient_registrations_national_id_hash'), 'patient_registrations', ['national_id_hash'], unique=False)

    # Backfill hash for existing rows by decrypting national_id
    # in-process (small table, one-off cost). Never do this pattern
    # for large PII tables - fine here given expected row counts.
    from app.core.encryption import decrypt_value_raw, hash_lookup_value

    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id, national_id FROM patient_registrations")).fetchall()
    for row in rows:
        plaintext = decrypt_value_raw(row.national_id)
        if plaintext:
            connection.execute(
                sa.text("UPDATE patient_registrations SET national_id_hash = :h WHERE id = :id"),
                {"h": hash_lookup_value(plaintext), "id": row.id},
            )

    # ---- hospital_api_keys ----
    op.create_table(
        'hospital_api_keys',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('hospital_id', sa.UUID(), nullable=False),
        sa.Column('label', sa.String(length=255), nullable=True),
        sa.Column('key_hash', sa.String(length=128), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_by_admin_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['hospital_id'], ['hospitals.id']),
        sa.ForeignKeyConstraint(['created_by_admin_id'], ['admin_users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_hospital_api_keys_hospital_id'), 'hospital_api_keys', ['hospital_id'], unique=False)
    op.create_index(op.f('ix_hospital_api_keys_key_hash'), 'hospital_api_keys', ['key_hash'], unique=True)

    # ---- patient_referrals ----
    op.create_table(
        'patient_referrals',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('hospital_id', sa.UUID(), nullable=False),
        sa.Column('patient_access_profile_id', sa.UUID(), nullable=True),
        sa.Column('source', postgresql.ENUM('MANUAL', 'API', name='referralsource', create_type=False), nullable=False),
        sa.Column('status', postgresql.ENUM('RECEIVED', 'MATCHED', 'REVIEWED', name='referralstatus', create_type=False), nullable=False),
        sa.Column('created_by_admin_id', sa.UUID(), nullable=True),
        sa.Column('api_key_id', sa.UUID(), nullable=True),
        sa.Column('first_name', sa.String(length=255), nullable=True),
        sa.Column('last_name', sa.String(length=255), nullable=True),
        sa.Column('national_id', sa.String(length=255), nullable=True),
        sa.Column('national_id_hash', sa.String(length=64), nullable=True),
        sa.Column('phone_number', sa.String(length=255), nullable=True),
        sa.Column('insurance_code', sa.String(length=255), nullable=True),
        sa.Column('chief_complaint', sa.Text(), nullable=True),
        sa.Column('primary_diagnosis', sa.Text(), nullable=True),
        sa.Column('secondary_diagnoses', sa.Text(), nullable=True),
        sa.Column('procedures_performed', sa.Text(), nullable=True),
        sa.Column('medical_history', sa.Text(), nullable=True),
        sa.Column('allergies', sa.Text(), nullable=True),
        sa.Column('vital_signs_summary', sa.Text(), nullable=True),
        sa.Column('discharge_medications', sa.Text(), nullable=True),
        sa.Column('care_instructions', sa.Text(), nullable=True),
        sa.Column('follow_up_recommendations', sa.Text(), nullable=True),
        sa.Column('additional_notes', sa.Text(), nullable=True),
        sa.Column('attending_physician_name', sa.String(length=255), nullable=True),
        sa.Column('referring_department_name', sa.String(length=255), nullable=True),
        sa.Column('admission_date', sa.Date(), nullable=True),
        sa.Column('discharge_date', sa.Date(), nullable=True),
        sa.Column('attachment_file_url', sa.String(length=1024), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['hospital_id'], ['hospitals.id']),
        sa.ForeignKeyConstraint(['patient_access_profile_id'], ['patient_access_profiles.id']),
        sa.ForeignKeyConstraint(['created_by_admin_id'], ['admin_users.id']),
        sa.ForeignKeyConstraint(['api_key_id'], ['hospital_api_keys.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_patient_referrals_hospital_id'), 'patient_referrals', ['hospital_id'], unique=False)
    op.create_index(op.f('ix_patient_referrals_patient_access_profile_id'), 'patient_referrals', ['patient_access_profile_id'], unique=False)
    op.create_index(op.f('ix_patient_referrals_status'), 'patient_referrals', ['status'], unique=False)
    op.create_index(op.f('ix_patient_referrals_national_id_hash'), 'patient_referrals', ['national_id_hash'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_patient_referrals_national_id_hash'), table_name='patient_referrals')
    op.drop_index(op.f('ix_patient_referrals_status'), table_name='patient_referrals')
    op.drop_index(op.f('ix_patient_referrals_patient_access_profile_id'), table_name='patient_referrals')
    op.drop_index(op.f('ix_patient_referrals_hospital_id'), table_name='patient_referrals')
    op.drop_table('patient_referrals')

    op.drop_index(op.f('ix_hospital_api_keys_key_hash'), table_name='hospital_api_keys')
    op.drop_index(op.f('ix_hospital_api_keys_hospital_id'), table_name='hospital_api_keys')
    op.drop_table('hospital_api_keys')

    op.drop_index(op.f('ix_patient_registrations_national_id_hash'), table_name='patient_registrations')
    op.drop_column('patient_registrations', 'national_id_hash')

    postgresql.ENUM(name='referralstatus').drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name='referralsource').drop(op.get_bind(), checkfirst=True)