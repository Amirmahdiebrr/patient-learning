"""
app/infrastructure/db/models/nurse.py

Nursing-staff accounts: a completely separate auth/portal from the
admin panel. A nurse self-registers with her nursing-council license
number and national ID under an already-active hospital (and
optionally one specific department), but stays inactive
(is_active=False) until a hospital admin approves her - she cannot
log in until then.
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.infrastructure.db.session import Base


class NurseUser(Base):
    __tablename__ = "nurse_users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    hospital_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=False, index=True)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True, index=True)

    full_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    national_id = Column(String(20), nullable=False)
    nursing_license_number = Column(String(50), nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)

    is_active = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    approved_at = Column(DateTime, nullable=True)

    hospital = relationship("Hospital")
    department = relationship("Department")