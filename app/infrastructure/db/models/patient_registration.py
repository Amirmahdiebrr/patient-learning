"""
app/infrastructure/db/models/patient_registration.py

Optional identity/contact info collected right after QR entry, on top
of the anonymous PatientAccessProfile. national_id, phone_number, and
insurance_code are encrypted at rest via EncryptedString - encryption
and decryption happen transparently on every write/read, no service
or route code touches ciphertext directly.
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
    phone_number = Column(EncryptedString(255), nullable=False)
    insurance_code = Column(EncryptedString(255), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    patient_access_profile = relationship("PatientAccessProfile", back_populates="registration")