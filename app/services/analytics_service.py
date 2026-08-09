"""
app/services/analytics_service.py

Read-only aggregation queries over existing tables (ProgressRecord,
QuizAttempt, PatientJourneyProfile, PatientAccessProfile). No new
storage - analytics are computed on demand from operational data.
"""

import uuid
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.infrastructure.db.models import (
    ProgressRecord, LessonProgressStatus, QuizAttempt, QuizQuestion,
    Lesson, EducationSection, PatientJourneyProfile, PatientAccessProfile,
    QRAccessPoint, JourneyStageCode,
)


def get_lesson_completion_rate(db: Session, hospital_id: uuid.UUID) -> dict:
    total = (
        db.query(func.count(ProgressRecord.id))
        .join(PatientAccessProfile, ProgressRecord.patient_access_profile_id == PatientAccessProfile.id)
        .join(QRAccessPoint, PatientAccessProfile.qr_access_point_id == QRAccessPoint.id)
        .filter(QRAccessPoint.hospital_id == hospital_id)
        .scalar()
    ) or 0

    completed = (
        db.query(func.count(ProgressRecord.id))
        .join(PatientAccessProfile, ProgressRecord.patient_access_profile_id == PatientAccessProfile.id)
        .join(QRAccessPoint, PatientAccessProfile.qr_access_point_id == QRAccessPoint.id)
        .filter(
            QRAccessPoint.hospital_id == hospital_id,
            ProgressRecord.status == LessonProgressStatus.COMPLETED,
        )
        .scalar()
    ) or 0

    rate = round((completed / total) * 100, 1) if total else 0.0
    return {"total_started": total, "total_completed": completed, "completion_rate_percent": rate}


def get_quiz_success_rate(db: Session, hospital_id: uuid.UUID) -> dict:
    total = (
        db.query(func.count(QuizAttempt.id))
        .join(PatientAccessProfile, QuizAttempt.patient_access_profile_id == PatientAccessProfile.id)
        .join(QRAccessPoint, PatientAccessProfile.qr_access_point_id == QRAccessPoint.id)
        .filter(QRAccessPoint.hospital_id == hospital_id)
        .scalar()
    ) or 0

    correct = (
        db.query(func.count(QuizAttempt.id))
        .join(PatientAccessProfile, QuizAttempt.patient_access_profile_id == PatientAccessProfile.id)
        .join(QRAccessPoint, PatientAccessProfile.qr_access_point_id == QRAccessPoint.id)
        .filter(QRAccessPoint.hospital_id == hospital_id, QuizAttempt.is_correct.is_(True))
        .scalar()
    ) or 0

    rate = round((correct / total) * 100, 1) if total else 0.0
    return {"total_attempts": total, "correct_attempts": correct, "success_rate_percent": rate}


def get_most_viewed_lessons(db: Session, hospital_id: uuid.UUID, limit: int = 10) -> list[dict]:
    rows = (
        db.query(Lesson.id, Lesson.title, func.count(ProgressRecord.id).label("view_count"))
        .join(ProgressRecord, ProgressRecord.lesson_id == Lesson.id)
        .join(PatientAccessProfile, ProgressRecord.patient_access_profile_id == PatientAccessProfile.id)
        .join(QRAccessPoint, PatientAccessProfile.qr_access_point_id == QRAccessPoint.id)
        .filter(QRAccessPoint.hospital_id == hospital_id)
        .group_by(Lesson.id, Lesson.title)
        .order_by(func.count(ProgressRecord.id).desc())
        .limit(limit)
        .all()
    )
    return [{"lesson_id": str(r.id), "title": r.title, "view_count": r.view_count} for r in rows]


def get_stage_distribution(db: Session, hospital_id: uuid.UUID) -> list[dict]:
    rows = (
        db.query(PatientJourneyProfile.current_stage, func.count(PatientJourneyProfile.id))
        .join(PatientAccessProfile, PatientJourneyProfile.patient_access_profile_id == PatientAccessProfile.id)
        .join(QRAccessPoint, PatientAccessProfile.qr_access_point_id == QRAccessPoint.id)
        .filter(QRAccessPoint.hospital_id == hospital_id, PatientJourneyProfile.is_active.is_(True))
        .group_by(PatientJourneyProfile.current_stage)
        .all()
    )
    return [{"stage": stage.value, "count": count} for stage, count in rows]


def get_today_new_patients(db: Session, hospital_id: uuid.UUID) -> int:
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return (
        db.query(func.count(PatientAccessProfile.id))
        .join(QRAccessPoint, PatientAccessProfile.qr_access_point_id == QRAccessPoint.id)
        .filter(QRAccessPoint.hospital_id == hospital_id, PatientAccessProfile.first_seen_at >= today_start)
        .scalar()
    ) or 0


def get_discharged_patient_count(db: Session, hospital_id: uuid.UUID, days: int = 30) -> int:
    since = datetime.utcnow() - timedelta(days=days)
    return (
        db.query(func.count(PatientJourneyProfile.id))
        .join(PatientAccessProfile, PatientJourneyProfile.patient_access_profile_id == PatientAccessProfile.id)
        .join(QRAccessPoint, PatientAccessProfile.qr_access_point_id == QRAccessPoint.id)
        .filter(
            QRAccessPoint.hospital_id == hospital_id,
            PatientJourneyProfile.current_stage == JourneyStageCode.DISCHARGE,
            PatientJourneyProfile.updated_at >= since,
        )
        .scalar()
    ) or 0


def get_average_lesson_completion_time_hours(db: Session, hospital_id: uuid.UUID) -> float | None:
    rows = (
        db.query(ProgressRecord.started_at, ProgressRecord.completed_at)
        .join(PatientAccessProfile, ProgressRecord.patient_access_profile_id == PatientAccessProfile.id)
        .join(QRAccessPoint, PatientAccessProfile.qr_access_point_id == QRAccessPoint.id)
        .filter(
            QRAccessPoint.hospital_id == hospital_id,
            ProgressRecord.status == LessonProgressStatus.COMPLETED,
            ProgressRecord.started_at.isnot(None),
            ProgressRecord.completed_at.isnot(None),
        )
        .all()
    )
    if not rows:
        return None

    total_hours = sum((r.completed_at - r.started_at).total_seconds() / 3600 for r in rows)
    return round(total_hours / len(rows), 2)


def get_hospital_dashboard_summary(db: Session, hospital_id: uuid.UUID) -> dict:
    return {
        "today_new_patients": get_today_new_patients(db, hospital_id),
        "discharged_last_30_days": get_discharged_patient_count(db, hospital_id, days=30),
        "lesson_completion": get_lesson_completion_rate(db, hospital_id),
        "quiz_success": get_quiz_success_rate(db, hospital_id),
        "average_completion_time_hours": get_average_lesson_completion_time_hours(db, hospital_id),
        "most_viewed_lessons": get_most_viewed_lessons(db, hospital_id, limit=5),
        "stage_distribution": get_stage_distribution(db, hospital_id),
    }