"""
app/infrastructure/db/models/medication.py

کاتالوگ داروها. department_type_id نال یعنی دارو «عمومی» است و برای
همه‌ی بخش‌ها نمایش داده می‌شود؛ در غیر این صورت فقط برای همان نوع بخش.
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.infrastructure.db.session import Base


class Medication(Base):
    __tablename__ = "medications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    department_type_id = Column(
        UUID(as_uuid=True), ForeignKey("standard_department_types.id"), nullable=True, index=True
    )

    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False, index=True)
    body_richtext = Column(Text, nullable=True)
    image_url = Column(String(1024), nullable=True)

    is_active = Column(Boolean, default=True, nullable=False)
    display_order = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    department_type = relationship("StandardDepartmentType", back_populates="medications")