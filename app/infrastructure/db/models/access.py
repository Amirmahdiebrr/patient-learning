"""
app/infrastructure/db/models/access.py

Access-gate domain models: Hospital, Department, QRAccessPoint,
PatientAccessProfile.

Design notes:
- QRAccessPoint.access_token is the only secret embedded in a printed
  QR code. It must be long, random and unguessable (never sequential).
- PatientAccessProfile has NO personally identifiable information.
  It exists purely so per-device progress/favorites/quiz-attempts can
  be tracked without real patient authentication.
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Column, String, Boolean, DateTime, ForeignKey, Enum, Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.infrastructure.db.session import Base


class QRAccessPointStatus(str, PyEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


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

    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    hospital = relationship("Hospital", back_populates="departments")
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
    Anonymous, device-bound profile. No PII. Created on first QR scan
    and persisted via a long-lived cookie so progress/favorites/quiz
    attempts can be attributed to "this device" without real auth.
    """
    __tablename__ = "patient_access_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    qr_access_point_id = Column(UUID(as_uuid=True), ForeignKey("qr_access_points.id"), nullable=False, index=True)
    device_fingerprint_hash = Column(String(128), nullable=True)  # optional, stats-only, never identifying

    first_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)