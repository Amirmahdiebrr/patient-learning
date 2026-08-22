# app/infrastructure/db/models/patient_procedure_selection.py
"""
app/infrastructure/db/models/patient_procedure_selection.py

Lets a patient select one or more Procedures relevant to them
(beyond the single procedure_id chosen at onboarding), editable any
time from their own profile. Used by content_targeting_service to
union before/after-procedure education across all of a patient's
selected procedures within their department.
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.infrastructure.db.session import Base


class PatientProcedureSelection(Base):
    __tablename__ = "patient_procedure_selections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    patient_access_profile_id = Column(
        UUID(as_uuid=True), ForeignKey("patient_access_profiles.id"), nullable=False, index=True
    )
    procedure_id = Column(UUID(as_uuid=True), ForeignKey("procedures.id"), nullable=False, index=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    procedure = relationship("Procedure")

    __table_args__ = (
        UniqueConstraint("patient_access_profile_id", "procedure_id", name="uq_patient_procedure_selection"),
    )