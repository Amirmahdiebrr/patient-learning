"""
app/infrastructure/db/models/admin.py

Admin identity + RBAC. A single admin_user can hold multiple roles,
each scoped to a specific hospital and/or department (nullable scope
= global, e.g. super_admin).
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.infrastructure.db.session import Base


class RoleCode(str, PyEnum):
    SUPER_ADMIN = "super_admin"
    HOSPITAL_ADMIN = "hospital_admin"
    DEPARTMENT_ADMIN = "department_admin"
    DOCTOR = "doctor"
    CONTENT_MANAGER = "content_manager"


class AdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_login_at = Column(DateTime, nullable=True)

    role_assignments = relationship("AdminRoleAssignment", back_populates="admin_user")


class Role(Base):
    __tablename__ = "roles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(Enum(RoleCode), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)

    assignments = relationship("AdminRoleAssignment", back_populates="role")


class AdminRoleAssignment(Base):
    """
    One admin can have several rows here, each scoping the same or
    different role to a different hospital/department. NULL scope
    fields mean "applies globally" (used for super_admin).
    """
    __tablename__ = "admin_role_assignments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    admin_user_id = Column(UUID(as_uuid=True), ForeignKey("admin_users.id"), nullable=False, index=True)
    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False, index=True)

    hospital_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=True, index=True)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True, index=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    admin_user = relationship("AdminUser", back_populates="role_assignments")
    role = relationship("Role", back_populates="assignments")