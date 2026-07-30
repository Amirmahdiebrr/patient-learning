"""
app/infrastructure/db/models/patient_interaction.py

Per-anonymous-profile interaction records: progress, favorites, quiz
attempts, feedback. All keyed by patient_access_profile_id, never by
any real identity field.
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Column, String, DateTime, ForeignKey, Enum, Text, Boolean, Integer
from sqlalchemy.dialects.postgresql import UUID

from app.infrastructure.db.session import Base


class LessonProgressStatus(str, PyEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class ProgressRecord(Base):
    __tablename__ = "progress_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_access_profile_id = Column(UUID(as_uuid=True), ForeignKey("patient_access_profiles.id"), nullable=False, index=True)
    lesson_id = Column(UUID(as_uuid=True), ForeignKey("lessons.id"), nullable=False, index=True)

    status = Column(Enum(LessonProgressStatus), default=LessonProgressStatus.NOT_STARTED, nullable=False)

    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class FavoriteRecord(Base):
    __tablename__ = "favorite_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_access_profile_id = Column(UUID(as_uuid=True), ForeignKey("patient_access_profiles.id"), nullable=False, index=True)
    lesson_id = Column(UUID(as_uuid=True), ForeignKey("lessons.id"), nullable=False, index=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_access_profile_id = Column(UUID(as_uuid=True), ForeignKey("patient_access_profiles.id"), nullable=False, index=True)
    question_id = Column(UUID(as_uuid=True), ForeignKey("quiz_questions.id"), nullable=False, index=True)
    selected_option_id = Column(UUID(as_uuid=True), ForeignKey("quiz_options.id"), nullable=False)

    is_correct = Column(Boolean, nullable=False)
    attempted_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class FeedbackRecord(Base):
    __tablename__ = "feedback_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_access_profile_id = Column(UUID(as_uuid=True), ForeignKey("patient_access_profiles.id"), nullable=False, index=True)
    lesson_id = Column(UUID(as_uuid=True), ForeignKey("lessons.id"), nullable=True, index=True)

    rating = Column(Integer, nullable=True)  # e.g. 1-5, nullable if only a comment is given
    comment = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)