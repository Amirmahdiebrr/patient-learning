# app/infrastructure/db/models/patient_journey.py
"""
app/infrastructure/db/models/patient_journey.py

Captures the onboarding questionnaire answers that route a patient's
educational content, and tracks which journey stage they're currently
in. procedure_id (optional) narrows content further within a
department - see content_targeting_service.py.
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Enum, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.infrastructure.db.session import Base
from app.infrastructure.db.models.content import JourneyStageCode


class PatientJourneyProfile(Base):
    __tablename__ = "patient_journey_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    patient_access_profile_id = Column(
        UUID(as_uuid=True), ForeignKey("patient_access_profiles.id"), nullable=False, index=True
    )

    disease_id = Column(UUID(as_uuid=True), ForeignKey("diseases.id"), nullable=True, index=True)
    treatment_id = Column(UUID(as_uuid=True), ForeignKey("treatments.id"), nullable=True, index=True)
    procedure_id = Column(UUID(as_uuid=True), ForeignKey("procedures.id"), nullable=True, index=True)
    has_surgery = Column(Boolean, nullable=True)
    age = Column(Integer, nullable=True)
    gender = Column(String(10), nullable=True)

    current_stage = Column(
        Enum(JourneyStageCode), nullable=False, default=JourneyStageCode.WELCOME
    )

    is_active = Column(Boolean, default=True, nullable=False)

    onboarding_completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    disease = relationship("Disease")
    treatment = relationship("Treatment")
    procedure = relationship("Procedure")