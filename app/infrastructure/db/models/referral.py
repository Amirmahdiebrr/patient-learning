"""
app/infrastructure/db/models/referral.py

Post-discharge referral / discharge-summary data sent to CuraLink by
a hospital, either manually (a staff member fills a form in the admin
panel) or via API (the hospital's own HIS calls our public endpoint
using a hospital-scoped API key).

All clinical fields are optional by design - hospitals vary wildly in
what they're able/willing to send, and CuraLink's job is to accept
whatever it gets, not enforce completeness.

Identity fields (name, national ID, phone, insurance code) are
encrypted at rest like PatientRegistration. national_id_hash enables
exact-match auto-linking to an existing PatientAccessProfile (via
PatientRegistration.national_id_hash) without decrypting every row -
see app/services/referral_matching_service.py.

patient_access_profile_id is nullable: a referral may arrive for a
patient who never scanned a QR at this hospital (referral-only
intake), or it may get auto-matched / manually linked later.
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Column, String, Text, Date, DateTime, ForeignKey, Enum, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.infrastructure.db.session import Base
from app.core.encryption import EncryptedString


class ReferralSource(str, PyEnum):
    MANUAL = "manual"
    API = "api"


class ReferralStatus(str, PyEnum):
    RECEIVED = "received"    # arrived, not yet linked to a known patient
    MATCHED = "matched"      # auto- or manually-linked to a PatientAccessProfile
    REVIEWED = "reviewed"    # staff has looked at it and marked it handled


class HospitalApiKey(Base):
    """
    One row = one API key issued to a hospital's HIS integration.
    Only the SHA-256 hash is stored - the raw key is shown to the
    admin exactly once, at creation time, and never again.
    """
    __tablename__ = "hospital_api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=False, index=True)

    label = Column(String(255), nullable=True)
    key_hash = Column(String(128), unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)

    created_by_admin_id = Column(UUID(as_uuid=True), ForeignKey("admin_users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    revoked_at = Column(DateTime, nullable=True)

    hospital = relationship("Hospital")


class PatientReferral(Base):
    __tablename__ = "patient_referrals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    hospital_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=False, index=True)
    patient_access_profile_id = Column(
        UUID(as_uuid=True), ForeignKey("patient_access_profiles.id"), nullable=True, index=True
    )

    source = Column(Enum(ReferralSource), nullable=False)
    status = Column(Enum(ReferralStatus), nullable=False, default=ReferralStatus.RECEIVED, index=True)

    created_by_admin_id = Column(UUID(as_uuid=True), ForeignKey("admin_users.id"), nullable=True)
    api_key_id = Column(UUID(as_uuid=True), ForeignKey("hospital_api_keys.id"), nullable=True)

    # ---- Identity (encrypted; hash for exact-match lookup) ----
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    national_id = Column(EncryptedString(255), nullable=True)
    national_id_hash = Column(String(64), nullable=True, index=True)
    phone_number = Column(EncryptedString(255), nullable=True)
    insurance_code = Column(EncryptedString(255), nullable=True)

    # ---- Clinical summary (all optional) ----
    chief_complaint = Column(Text, nullable=True)
    primary_diagnosis = Column(Text, nullable=True)
    secondary_diagnoses = Column(Text, nullable=True)
    procedures_performed = Column(Text, nullable=True)
    medical_history = Column(Text, nullable=True)
    allergies = Column(Text, nullable=True)
    vital_signs_summary = Column(Text, nullable=True)
    discharge_medications = Column(Text, nullable=True)
    care_instructions = Column(Text, nullable=True)
    follow_up_recommendations = Column(Text, nullable=True)
    additional_notes = Column(Text, nullable=True)

    attending_physician_name = Column(String(255), nullable=True)
    referring_department_name = Column(String(255), nullable=True)  # free text - hospital's own naming
    admission_date = Column(Date, nullable=True)
    discharge_date = Column(Date, nullable=True)

    attachment_file_url = Column(String(1024), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    hospital = relationship("Hospital")
    patient_access_profile = relationship("PatientAccessProfile")