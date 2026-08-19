# app/infrastructure/db/models/procedure.py
"""
app/infrastructure/db/models/procedure.py

Procedure catalog, scoped to a StandardDepartmentType. Optional layer
between Department and Stage: EducationSection.procedure_id and
QuizQuestion.procedure_id (nullable) let content be either
department-general (procedure_id NULL) or procedure-specific.
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.infrastructure.db.session import Base


class Procedure(Base):
    __tablename__ = "procedures"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    department_type_id = Column(
        UUID(as_uuid=True), ForeignKey("standard_department_types.id"), nullable=False, index=True
    )

    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    display_order = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    department_type = relationship("StandardDepartmentType", back_populates="procedures")