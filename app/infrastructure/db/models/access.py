# app/infrastructure/db/models/access.py
"""
app/infrastructure/db/models/access.py
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

    # اطلاعات ثبت‌نام / تماس بیمارستان و مسئول آن - برای بررسی ادمین قبل از تایید
    address = Column(String(500), nullable=True)
    phone_number = Column(String(20), nullable=True)
    responsible_phone = Column(String(20), nullable=True)
    responsible_national_id = Column(String(20), nullable=True)

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
    __tablename__ = "qr_access_points"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    hospital_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=False, index=True)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id"), nullable=False, index=True)

    access_token = Column(String(128), unique=True, nullable=False, index=True)
    label = Column(String(255), nullable=True)

    status = Column(Enum(QRAccessPointStatus), default=QRAccessPointStatus.ACTIVE, nullable=False, index=True)

    created_by_admin_id = Column(UUID(as_uuid=True), ForeignKey("admin_users.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    revoked_at = Column(DateTime, nullable=True)

    hospital = relationship("Hospital", back_populates="qr_access_points")
    department = relationship("Department", back_populates="qr_access_points")


class PatientAccessProfile(Base):
    __tablename__ = "patient_access_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    qr_access_point_id = Column(UUID(as_uuid=True), ForeignKey("qr_access_points.id"), nullable=True, index=True)
    hospital_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=True, index=True)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True, index=True)

    device_fingerprint_hash = Column(String(128), nullable=True)

    first_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    qr_access_point = relationship("QRAccessPoint")
    hospital = relationship("Hospital")
    department = relationship("Department")
    registration = relationship("PatientRegistration", back_populates="patient_access_profile", uselist=False)