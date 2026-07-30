"""
app/infrastructure/db/models/patient_journey.py

Captures the onboarding questionnaire answers that route a patient's
educational content, and tracks which journey stage they're currently
in. Still fully anonymous - no name, no national ID, no phone.
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Enum, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.infrastructure.db.session import Base
from app.infrastructure.db.models.content import JourneyStageCode


class PatientJourneyProfile(Base):
    """
    One row per "hospital visit" of an anonymous patient device.
    A single PatientAccessProfile (device) could in theory start a
    new journey on a later visit, so this is 1-to-many from
    PatientAccessProfile, but only one journey is "active" at a time
    (is_active=True) and the app always reads/writes the active one.
    """
    __tablename__ = "patient_journey_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    patient_access_profile_id = Column(
        UUID(as_uuid=True), ForeignKey("patient_access_profiles.id"), nullable=False, index=True
    )

    # Answered during onboarding, right after QR scan
    disease_id = Column(UUID(as_uuid=True), ForeignKey("diseases.id"), nullable=True, index=True)
    treatment_id = Column(UUID(as_uuid=True), ForeignKey("treatments.id"), nullable=True, index=True)
    has_surgery = Column(Boolean, nullable=True)
    age = Column(Integer, nullable=True)
    gender = Column(String(10), nullable=True)  # "male" | "female" | "other"

    # Tracks where the patient currently is in the journey, so the app
    # knows which stage's lessons to surface first (e.g. after a nurse
    # or the patient advances it post-admission or post-discharge).
    current_stage = Column(
        Enum(JourneyStageCode), nullable=False, default=JourneyStageCode.WELCOME
    )

    is_active = Column(Boolean, default=True, nullable=False)

    onboarding_completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    disease = relationship("Disease")
    treatment = relationship("Treatment")