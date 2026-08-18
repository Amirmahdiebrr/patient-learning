"""
app/services/patient_monitoring_service.py

Nurse/doctor-facing per-patient learning monitoring: for each patient
registered under a hospital (optionally scoped to one department),
computes how much of their assigned educational content they've
actually completed, their quiz performance, and how long since their
last activity - then flags patients who need follow-up (inactive too
long, or repeatedly failing quizzes). Read-only aggregation over
existing tables, no new storage.
"""

import uuid
from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from app.infrastructure.db.models import (
    PatientRegistration, PatientAccessProfile, PatientJourneyProfile,
    QRAccessPoint, Hospital, Department,
    ProgressRecord, LessonProgressStatus, QuizAttempt,
)
from app.services.content_targeting_service import get_lessons_for_journey
from app.core.encryption import blind_index

INACTIVITY_THRESHOLD_DAYS = 3
LOW_QUIZ_SUCCESS_PERCENT = 50.0
MIN_QUIZ_ATTEMPTS_FOR_FLAG = 3

STAGE_DISPLAY_NAMES = {
    "welcome": "خوش‌آمدگویی",
    "admission": "پذیرش در بخش",
    "before_procedure": "قبل از عمل",
    "procedure": "حین عمل",
    "after_procedure": "بعد از عمل",
    "daily_inpatient": "آموزش روزانه‌ی بستری",
    "discharge": "ترخیص",
    "home_care": "مراقبت در منزل",
    "follow_up": "پیگیری",
    "long_term_monitoring": "پایش بلندمدت",
}


def _resolve_hospital_department(db: Session, profile: PatientAccessProfile):
    if profile.hospital_id and profile.department_id:
        hospital = db.query(Hospital).filter(Hospital.id == profile.hospital_id).first()
        department = db.query(Department).filter(Department.id == profile.department_id).first()
        return hospital, department

    qr = db.query(QRAccessPoint).filter(QRAccessPoint.id == profile.qr_access_point_id).first()
    if not qr:
        return None, None
    return qr.hospital, qr.department


def _build_row(db: Session, registration: PatientRegistration) -> dict | None:
    profile = registration.patient_access_profile
    hospital, department = _resolve_hospital_department(db, profile)
    if not hospital or not department:
        return None

    journey = (
        db.query(PatientJourneyProfile)
        .filter(
            PatientJourneyProfile.patient_access_profile_id == profile.id,
            PatientJourneyProfile.is_active.is_(True),
        )
        .order_by(PatientJourneyProfile.created_at.desc())
        .first()
    )

    current_stage_total = 0
    current_stage_completed = 0
    current_stage_code = "welcome"

    if journey and journey.onboarding_completed_at:
        current_stage_code = journey.current_stage.value
        stage_lessons = get_lessons_for_journey(
            db, journey,
            hospital_id=hospital.id,
            department_id=department.id,
            department_type_id=department.department_type_id,
        )
        current_stage_total = len(stage_lessons)
        if stage_lessons:
            lesson_ids = [l.id for l in stage_lessons]
            current_stage_completed = (
                db.query(ProgressRecord)
                .filter(
                    ProgressRecord.patient_access_profile_id == profile.id,
                    ProgressRecord.lesson_id.in_(lesson_ids),
                    ProgressRecord.status == LessonProgressStatus.COMPLETED,
                )
                .count()
            )

    total_lessons_completed = (
        db.query(ProgressRecord)
        .filter(
            ProgressRecord.patient_access_profile_id == profile.id,
            ProgressRecord.status == LessonProgressStatus.COMPLETED,
        )
        .count()
    )

    quiz_total = (
        db.query(QuizAttempt)
        .filter(QuizAttempt.patient_access_profile_id == profile.id)
        .count()
    )
    quiz_correct = (
        db.query(QuizAttempt)
        .filter(
            QuizAttempt.patient_access_profile_id == profile.id,
            QuizAttempt.is_correct.is_(True),
        )
        .count()
    )
    quiz_success_percent = round((quiz_correct / quiz_total) * 100, 1) if quiz_total else 0.0

    last_progress = (
        db.query(ProgressRecord.updated_at)
        .filter(ProgressRecord.patient_access_profile_id == profile.id)
        .order_by(ProgressRecord.updated_at.desc())
        .first()
    )
    last_quiz = (
        db.query(QuizAttempt.attempted_at)
        .filter(QuizAttempt.patient_access_profile_id == profile.id)
        .order_by(QuizAttempt.attempted_at.desc())
        .first()
    )

    candidates = [profile.last_seen_at]
    if last_progress and last_progress[0]:
        candidates.append(last_progress[0])
    if last_quiz and last_quiz[0]:
        candidates.append(last_quiz[0])
    last_activity_at = max(candidates) if candidates else None

    days_inactive = (datetime.utcnow() - last_activity_at).days if last_activity_at else None
    days_since_registration = (datetime.utcnow() - registration.created_at).days

    onboarding_completed = bool(journey and journey.onboarding_completed_at)

    needs_attention = False
    if onboarding_completed:
        if days_inactive is not None and days_inactive >= INACTIVITY_THRESHOLD_DAYS:
            needs_attention = True
        if quiz_total >= MIN_QUIZ_ATTEMPTS_FOR_FLAG and quiz_success_percent < LOW_QUIZ_SUCCESS_PERCENT:
            needs_attention = True
    else:
        if days_since_registration >= INACTIVITY_THRESHOLD_DAYS:
            needs_attention = True

    current_stage_percent = (
        round((current_stage_completed / current_stage_total) * 100, 1) if current_stage_total else 0.0
    )

    return {
        "patient_access_profile_id": profile.id,
        "first_name": registration.first_name,
        "last_name": registration.last_name,
        "hospital_name": hospital.name,
        "department_name": department.name,
        "current_stage_code": current_stage_code,
        "current_stage_name": STAGE_DISPLAY_NAMES.get(current_stage_code, current_stage_code),
        "current_stage_lessons_total": current_stage_total,
        "current_stage_lessons_completed": current_stage_completed,
        "current_stage_percent": current_stage_percent,
        "total_lessons_completed": total_lessons_completed,
        "quiz_total": quiz_total,
        "quiz_correct": quiz_correct,
        "quiz_success_percent": quiz_success_percent,
        "onboarding_completed": onboarding_completed,
        "days_since_registration": days_since_registration,
        "last_activity_at": last_activity_at,
        "days_inactive": days_inactive,
        "needs_attention": needs_attention,
    }


def get_patient_monitoring(
    db: Session,
    hospital_id: uuid.UUID,
    department_id: uuid.UUID | None,
    search: str | None,
    only_needs_attention: bool,
    limit: int,
    offset: int,
) -> tuple[int, list[dict]]:
    query = (
        db.query(PatientRegistration)
        .join(PatientAccessProfile, PatientRegistration.patient_access_profile_id == PatientAccessProfile.id)
        .outerjoin(QRAccessPoint, PatientAccessProfile.qr_access_point_id == QRAccessPoint.id)
        .options(joinedload(PatientRegistration.patient_access_profile))
        .filter(
            (PatientAccessProfile.hospital_id == hospital_id) | (QRAccessPoint.hospital_id == hospital_id)
        )
    )

    if department_id:
        query = query.filter(
            (PatientAccessProfile.department_id == department_id) | (QRAccessPoint.department_id == department_id)
        )

    if search:
        term = search.strip()
        if term.isdigit():
            digit_hash = blind_index(term)
            query = query.filter(
                (PatientRegistration.national_id_hash == digit_hash)
                | (PatientRegistration.phone_number_hash == digit_hash)
            )
        else:
            like_term = f"%{term}%"
            query = query.filter(
                (PatientRegistration.first_name.ilike(like_term))
                | (PatientRegistration.last_name.ilike(like_term))
            )

    registrations = query.order_by(PatientRegistration.created_at.desc()).all()

    rows = []
    for reg in registrations:
        row = _build_row(db, reg)
        if row is None:
            continue
        if only_needs_attention and not row["needs_attention"]:
            continue
        rows.append(row)

    rows.sort(key=lambda r: (
        not r["needs_attention"],
        r["last_activity_at"] or datetime.min,
    ))

    total = len(rows)
    return total, rows[offset:offset + limit]