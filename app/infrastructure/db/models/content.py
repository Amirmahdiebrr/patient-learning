"""
app/infrastructure/db/models/content.py

Educational content domain: Disease, Treatment, JourneyStage,
EducationSection, Lesson, MediaAsset, QuizQuestion, QuizOption.

Design notes:
- JourneyStage is a fixed lookup table (11 rows, seeded once), NOT
  per-treatment. Every treatment reuses the same stage vocabulary.
- EducationSection.treatment_id is nullable: some sections are
  general (hospital-wide) education, not tied to a specific treatment.
- EducationSection.department_type_id is nullable and links to the
  standard department taxonomy (StandardDepartmentType), NOT to a
  specific hospital's Department row. This makes content a shared
  library: build it once per department type (e.g. "Orthopedics"),
  and it automatically applies to every hospital that has a
  Department of that type - no per-hospital linking needed.
  NULL means "general education shown regardless of department type".
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


class JourneyStageCode(str, PyEnum):
    WELCOME = "welcome"
    GENERAL_EDUCATION = "general_education"
    DEPARTMENT_INTRO = "department_intro"
    ADMISSION = "admission"
    BEFORE_PROCEDURE = "before_procedure"
    PROCEDURE = "procedure"
    AFTER_PROCEDURE = "after_procedure"
    DAILY_INPATIENT = "daily_inpatient"
    DISCHARGE = "discharge"
    HOME_CARE = "home_care"
    FOLLOW_UP = "follow_up"
    LONG_TERM_MONITORING = "long_term_monitoring"


class MediaType(str, PyEnum):
    VIDEO = "video"
    IMAGE = "image"
    PDF = "pdf"
    ANIMATION = "animation"


class Disease(Base):
    __tablename__ = "diseases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    treatments = relationship("Treatment", back_populates="disease")


class Treatment(Base):
    __tablename__ = "treatments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    disease_id = Column(UUID(as_uuid=True), ForeignKey("diseases.id"), nullable=False, index=True)

    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    disease = relationship("Disease", back_populates="treatments")
    sections = relationship("EducationSection", back_populates="treatment")


class JourneyStage(Base):
    """
    Fixed lookup table, seeded once via migration/seed script.
    Do not create these dynamically from admin panel in phase 1.
    """
    __tablename__ = "journey_stages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(Enum(JourneyStageCode), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    display_order = Column(Integer, nullable=False)

    sections = relationship("EducationSection", back_populates="journey_stage")


class EducationSection(Base):
    __tablename__ = "education_sections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    journey_stage_id = Column(UUID(as_uuid=True), ForeignKey("journey_stages.id"), nullable=False, index=True)
    treatment_id = Column(UUID(as_uuid=True), ForeignKey("treatments.id"), nullable=True, index=True)
    department_type_id = Column(
        UUID(as_uuid=True), ForeignKey("standard_department_types.id"), nullable=True, index=True
    )

    title = Column(String(255), nullable=False)
    display_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    journey_stage = relationship("JourneyStage", back_populates="sections")
    treatment = relationship("Treatment", back_populates="sections")
    department_type = relationship("StandardDepartmentType", back_populates="education_sections")
    lessons = relationship("Lesson", back_populates="section", order_by="Lesson.display_order")


class Lesson(Base):
    __tablename__ = "lessons"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    section_id = Column(UUID(as_uuid=True), ForeignKey("education_sections.id"), nullable=False, index=True)

    title = Column(String(255), nullable=False)
    body_richtext = Column(Text, nullable=True)
    display_order = Column(Integer, nullable=False, default=0)
    is_published = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    section = relationship("EducationSection", back_populates="lessons")
    media_assets = relationship("MediaAsset", back_populates="lesson", order_by="MediaAsset.display_order", cascade="all, delete-orphan")
    quiz_questions = relationship("QuizQuestion", back_populates="lesson", cascade="all, delete-orphan")
    targeting_rules = relationship("ContentTargetingRule", back_populates="lesson")


class MediaAsset(Base):
    __tablename__ = "media_assets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lesson_id = Column(UUID(as_uuid=True), ForeignKey("lessons.id"), nullable=False, index=True)

    type = Column(Enum(MediaType), nullable=False)
    file_url = Column(String(1024), nullable=False)
    thumbnail_url = Column(String(1024), nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    display_order = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    lesson = relationship("Lesson", back_populates="media_assets")


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lesson_id = Column(UUID(as_uuid=True), ForeignKey("lessons.id"), nullable=False, index=True)

    question_text = Column(Text, nullable=False)
    display_order = Column(Integer, nullable=False, default=0)

    lesson = relationship("Lesson", back_populates="quiz_questions")
    options = relationship("QuizOption", back_populates="question", order_by="QuizOption.display_order", cascade="all, delete-orphan")


class QuizOption(Base):
    __tablename__ = "quiz_options"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id = Column(UUID(as_uuid=True), ForeignKey("quiz_questions.id"), nullable=False, index=True)

    option_text = Column(String(500), nullable=False)
    is_correct = Column(Boolean, default=False, nullable=False)
    display_order = Column(Integer, nullable=False, default=0)

    question = relationship("QuizQuestion", back_populates="options")


class ContentTargetingRule(Base):
    """
    Fine-grained OPTIONAL override on top of the department_type match:
    a lesson can have MULTIPLE rules for extra filtering by age/gender/
    disease/treatment, or to further restrict to one specific hospital
    or one specific Department row (rarely needed now that
    EducationSection.department_type_id handles the common case).
    A lesson is shown if AT LEAST ONE of its rules matches; a lesson
    with zero rules is shown to everyone matching the structural
    (journey_stage + department_type) layer.
    """
    __tablename__ = "content_targeting_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lesson_id = Column(UUID(as_uuid=True), ForeignKey("lessons.id"), nullable=False, index=True)

    hospital_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=True, index=True)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True, index=True)
    disease_id = Column(UUID(as_uuid=True), ForeignKey("diseases.id"), nullable=True, index=True)
    treatment_id = Column(UUID(as_uuid=True), ForeignKey("treatments.id"), nullable=True, index=True)

    min_age = Column(Integer, nullable=True)
    max_age = Column(Integer, nullable=True)
    gender = Column(String(10), nullable=True)  # "male" | "female" | "other" | null (any)

    priority = Column(Integer, nullable=False, default=0)

    lesson = relationship("Lesson", back_populates="targeting_rules")