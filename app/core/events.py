"""
app/core/events.py

Domain event definitions for CuraLink. These are plain, immutable
data carriers - they describe "something happened" and hold just
enough context for a handler to act on it. They intentionally do NOT
hold live ORM objects (to avoid handlers accidentally re-using a
detached SQLAlchemy session) - only primitive/UUID identifiers and
simple values.

Adding a new event type here does nothing by itself; something must
call event_bus.publish(...) with an instance of it, and something
must event_bus.subscribe(...) a handler to it (see
app/services/event_handlers/).
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
    """
    Defined now, not yet published anywhere. Will be wired into the
    Patient Journey State Machine work, which is the first place that
    will actually know when a patient transitions to the DISCHARGE
    stage in a principled way.
    """
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
    """
    Covers create/update/delete/publish/unpublish on any content
    object (hospital, department, education_section, lesson,
    media_asset, quiz_question, targeting_rule). object_type/object_id
    identify what was touched; before/after hold plain-dict snapshots
    (None for create/delete where one side doesn't apply).
    """
    admin_id: uuid.UUID
    action: str  # "create" | "update" | "delete" | "publish" | "unpublish" | "deactivate" | "reactivate"
    object_type: str
    object_id: uuid.UUID
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    ip_address: str | None = None


@dataclass(kw_only=True)
class AdminAccessAction(DomainEvent):
    """
    Covers admin user / role-assignment changes and patient-report
    views - anything touching who-can-see-what or actual patient PII
    access, which needs its own audit trail regardless of content
    changes.
    """
    admin_id: uuid.UUID
    action: str  # "create_admin" | "deactivate_admin" | "assign_role" | "revoke_role" | "view_patient_report"
    object_type: str
    object_id: uuid.UUID | None = None
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    ip_address: str | None = None