# app/infrastructure/db/models/patient_registration.py
"""
app/infrastructure/db/models/patient_registration.py

Optional identity/contact info collected right after QR entry (or
directly at self-service registration), on top of the anonymous
PatientAccessProfile. national_id, phone_number, and insurance_code
are encrypted at rest via EncryptedString.

national_id_hash / phone_number_hash are deterministic HMAC-SHA256
digests (see app/core/encryption.blind_index) stored alongside the
encrypted values purely to allow exact-match lookups (e.g. matching
an incoming PatientReferral, searching the admin patient report, or
looking a patient up by national ID at self-service login) without
decrypting every row in the table.

password_hash is set only for patients who registered/logged in
through the self-service panel (see app/api/v1/patient_self_auth.py).
Patients who only ever entered via QR never set a password and can't
use the self-service login - they can still browse via the QR-issued
cookies.
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.infrastructure.db.session import Base
from app.core.encryption import EncryptedString


class PatientRegistration(Base):
    __tablename__ = "patient_registrations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    patient_access_profile_id = Column(
        UUID(as_uuid=True), ForeignKey("patient_access_profiles.id"),
        nullable=False, unique=True, index=True,
    )

    first_name = Column(String(255), nullable=False)
    last_name = Column(String(255), nullable=False)
    national_id = Column(EncryptedString(255), nullable=False)
    national_id_hash = Column(String(64), nullable=True, index=True)
    phone_number = Column(EncryptedString(255), nullable=False)
    phone_number_hash = Column(String(64), nullable=True, index=True)
    insurance_code = Column(EncryptedString(255), nullable=True)

    password_hash = Column(String(255), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    patient_access_profile = relationship("PatientAccessProfile", back_populates="registration")