"""
app/infrastructure/db/models/__init__.py

Imports every model module so that Base.metadata is fully populated
before Alembic autogenerate or Base.metadata.create_all() runs.
"""

from app.infrastructure.db.models.access import (
    Hospital,
    Department,
    QRAccessPoint,
    QRAccessPointStatus,
    PatientAccessProfile,
)
from app.infrastructure.db.models.content import (
    Disease,
    Treatment,
    JourneyStage,
    JourneyStageCode,
    EducationSection,
    Lesson,
    MediaAsset,
    MediaType,
    QuizQuestion,
    QuizOption,
    ContentTargetingRule,
)
from app.infrastructure.db.models.patient_interaction import (
    ProgressRecord,
    LessonProgressStatus,
    FavoriteRecord,
    QuizAttempt,
    FeedbackRecord,
)
from app.infrastructure.db.models.patient_journey import PatientJourneyProfile
from app.infrastructure.db.models.admin import (
    AdminUser,
    Role,
    RoleCode,
    AdminRoleAssignment,
)

__all__ = [
    "Hospital",
    "Department",
    "QRAccessPoint",
    "QRAccessPointStatus",
    "PatientAccessProfile",
    "Disease",
    "Treatment",
    "JourneyStage",
    "JourneyStageCode",
    "EducationSection",
    "Lesson",
    "MediaAsset",
    "MediaType",
    "QuizQuestion",
    "QuizOption",
    "ContentTargetingRule",
    "ProgressRecord",
    "LessonProgressStatus",
    "FavoriteRecord",
    "QuizAttempt",
    "FeedbackRecord",
    "PatientJourneyProfile",
    "AdminUser",
    "Role",
    "RoleCode",
    "AdminRoleAssignment",
]