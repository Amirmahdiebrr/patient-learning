"""
app/infrastructure/db/models/__init__.py
"""

from app.infrastructure.db.models.access import (
    Hospital, Department, QRAccessPoint, QRAccessPointStatus,
    PatientAccessProfile, StandardDepartmentType, DepartmentMacroCategory,
)
from app.infrastructure.db.models.content import (
    Disease, Treatment, JourneyStage, JourneyStageCode, EducationSection,
    Lesson, MediaAsset, MediaType, QuizQuestion, QuizOption,
    ContentTargetingRule, LessonOverrideLevel,
)
from app.infrastructure.db.models.patient_interaction import (
    ProgressRecord, LessonProgressStatus, FavoriteRecord, QuizAttempt, FeedbackRecord,
)
from app.infrastructure.db.models.patient_journey import PatientJourneyProfile
from app.infrastructure.db.models.patient_registration import PatientRegistration
from app.infrastructure.db.models.audit_log import AuditLog
from app.infrastructure.db.models.followup import FollowUpTask, FollowUpChannel, FollowUpStatus
from app.infrastructure.db.models.admin import AdminUser, Role, RoleCode, AdminRoleAssignment

__all__ = [
    "Hospital", "Department", "QRAccessPoint", "QRAccessPointStatus",
    "PatientAccessProfile", "StandardDepartmentType", "DepartmentMacroCategory",
    "Disease", "Treatment", "JourneyStage", "JourneyStageCode", "EducationSection",
    "Lesson", "MediaAsset", "MediaType", "QuizQuestion", "QuizOption",
    "ContentTargetingRule", "LessonOverrideLevel",
    "ProgressRecord", "LessonProgressStatus", "FavoriteRecord", "QuizAttempt", "FeedbackRecord",
    "PatientJourneyProfile", "PatientRegistration", "AuditLog",
    "FollowUpTask", "FollowUpChannel", "FollowUpStatus",
    "AdminUser", "Role", "RoleCode", "AdminRoleAssignment",
]