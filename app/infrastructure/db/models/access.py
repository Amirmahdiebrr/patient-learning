"""
app/infrastructure/db/models/access.py

Access-gate domain models: Hospital, Department, QRAccessPoint,
PatientAccessProfile, plus the standardized department taxonomy
(StandardDepartmentType) used to classify departments consistently
across hospitals.

Design notes:
- QRAccessPoint.access_token is the only secret embedded in a printed
  QR code. It must be long, random and unguessable (never sequential).
- PatientAccessProfile itself has NO personally identifiable
  information - it exists purely so per-device progress/favorites/
  quiz-attempts can be tracked without real patient authentication.
  Real identity (name, national ID, phone) lives in the separate,
  optional PatientRegistration table (one-to-one), kept apart so the
  device-tracking mechanism stays PII-free at its core even though
  most hospitals will now also collect a PatientRegistration.
- StandardDepartmentType is a fixed lookup (seeded once via
  scripts/seed_department_types.py) representing the standard Iranian
  hospital department taxonomy. Department.department_type_id links a
  hospital's actual department to this type - this is what lets a
  hospital "attach" a shared content library (built once per
  department type via EducationSection.department_type_id) simply by
  choosing a type when creating the department, with no per-hospital
  content re-linking needed.
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Column, String, Boolean, DateTime, ForeignKey, Enum, Text, Integer,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.infrastructure.db.session import Base


class QRAccessPointStatus(str, PyEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


class DepartmentMacroCategory(str, PyEnum):
    SURGICAL = "surgical"
    MEDICAL = "medical"
    CRITICAL_CARE = "critical_care"
    OBSTETRICS_GYNECOLOGY = "obstetrics_gynecology"
    PEDIATRICS = "pediatrics"
    OUTPATIENT_PROCEDURES = "outpatient_procedures"


class StandardDepartmentType(Base):
    """
    Fixed lookup table, seeded once via scripts/seed_department_types.py.
    Represents the standard Iranian hospital department taxonomy
    (macro category -> specific department). This is the shared
    "content library key": EducationSection rows link to it directly,
    and Department rows link to it to say "this hospital's department
    is of this type" - matching the two automatically attaches the
    right content to the right hospital department, with zero manual
    per-hospital linking.
    """
    __tablename__ = "standard_department_types"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    macro_category = Column(Enum(DepartmentMacroCategory), nullable=False, index=True)
    code = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    display_order = Column(Integer, nullable=False, default=0)

    departments = relationship("Department", back_populates="department_type")
    education_sections = relationship("EducationSection", back_populates="department_type")


class Hospital(Base):
    __tablename__ = "hospitals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    departments = relationship("Department", back_populates="hospital")
    qr_access_points = relationship("QRAccessPoint", back_populates="hospital")


class Department(Base):
    __tablename__ = "departments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=False, index=True)
    department_type_id = Column(
        UUID(as_uuid=True), ForeignKey("standard_department_types.id"), nullable=True, index=True
    )

    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    hospital = relationship("Hospital", back_populates="departments")
    department_type = relationship("StandardDepartmentType", back_populates="departments")
    qr_access_points = relationship("QRAccessPoint", back_populates="department")


class QRAccessPoint(Base):
    """
    One row = one physically printed QR code, bound to a hospital +
    department. Reusable by many patients; revocable independently.
    """
    __tablename__ = "qr_access_points"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    hospital_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=False, index=True)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id"), nullable=False, index=True)

    access_token = Column(String(128), unique=True, nullable=False, index=True)
    label = Column(String(255), nullable=True)  # admin-facing description, e.g. "Orthopedics ward entrance"

    status = Column(Enum(QRAccessPointStatus), default=QRAccessPointStatus.ACTIVE, nullable=False, index=True)

    created_by_admin_id = Column(UUID(as_uuid=True), ForeignKey("admin_users.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    revoked_at = Column(DateTime, nullable=True)

    hospital = relationship("Hospital", back_populates="qr_access_points")
    department = relationship("Department", back_populates="qr_access_points")


class PatientAccessProfile(Base):
    """
    Anonymous, device-bound profile. Core fields carry NO PII by
    design. Created on first QR scan and persisted via a long-lived
    cookie so progress/favorites/quiz-attempts can be attributed to
    "this device" without real auth. May optionally have a linked
    PatientRegistration row (one-to-one) holding real identity/contact
    info once the hospital collects it.
    """
    __tablename__ = "patient_access_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    qr_access_point_id = Column(UUID(as_uuid=True), ForeignKey("qr_access_points.id"), nullable=False, index=True)
    device_fingerprint_hash = Column(String(128), nullable=True)  # optional, stats-only, never identifying

    first_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    qr_access_point = relationship("QRAccessPoint")
    registration = relationship("PatientRegistration", back_populates="patient_access_profile", uselist=False)