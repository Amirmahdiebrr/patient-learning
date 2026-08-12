"""
app/core/events.py
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(kw_only=True)
class DomainEvent:
    occurred_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(kw_only=True)
class QRScanned(DomainEvent):
    qr_access_point_id: uuid.UUID
    patient_access_profile_id: uuid.UUID
    hospital_id: uuid.UUID
    department_id: uuid.UUID
    is_new_profile: bool


@dataclass(kw_only=True)
class PatientRegistered(DomainEvent):
    patient_access_profile_id: uuid.UUID
    hospital_id: uuid.UUID
    department_id: uuid.UUID


@dataclass(kw_only=True)
class PatientStageChanged(DomainEvent):
    patient_access_profile_id: uuid.UUID
    journey_id: uuid.UUID
    old_stage: str
    new_stage: str


@dataclass(kw_only=True)
class PatientDischarged(DomainEvent):
    patient_access_profile_id: uuid.UUID
    hospital_id: uuid.UUID


@dataclass(kw_only=True)
class LessonCompleted(DomainEvent):
    patient_access_profile_id: uuid.UUID
    lesson_id: uuid.UUID


@dataclass(kw_only=True)
class QuizCompleted(DomainEvent):
    patient_access_profile_id: uuid.UUID
    question_id: uuid.UUID
    is_correct: bool


@dataclass(kw_only=True)
class AIConversationStarted(DomainEvent):
    patient_access_profile_id: uuid.UUID
    question: str


@dataclass(kw_only=True)
class AdminContentAction(DomainEvent):
    admin_id: uuid.UUID
    action: str
    object_type: str
    object_id: uuid.UUID
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    ip_address: str | None = None


@dataclass(kw_only=True)
class AdminAccessAction(DomainEvent):
    admin_id: uuid.UUID
    action: str
    object_type: str
    object_id: uuid.UUID | None = None
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    ip_address: str | None = None


@dataclass(kw_only=True)
class ReferralReceived(DomainEvent):
    referral_id: uuid.UUID
    hospital_id: uuid.UUID
    source: str  # "manual" | "api"
    matched: bool