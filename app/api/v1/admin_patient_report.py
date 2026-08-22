# app/api/v1/admin_patient_report.py
"""
app/api/v1/admin_patient_report.py

Admin-only read report of registered patients: identity/contact info
(PatientRegistration) joined with their current journey stage/health
routing info (PatientJourneyProfile) and which hospital/department
they registered through (via QRAccessPoint OR the profile's own
hospital_id/department_id for self-service patients). Scoped by
hospital/department like other admin endpoints - a hospital_admin or
department_admin only sees patients registered under their scope;
super_admin sees everyone.

Also exposes /patient-report/{id}/progress: full lesson-by-lesson
progress + quiz stats for one patient, so a hospital admin/super_admin
can see exactly how far a referred patient has gotten in their
education, not just the referral's clinical fields.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import (
    AdminUser, PatientRegistration, PatientAccessProfile, PatientJourneyProfile,
    QRAccessPoint, Hospital, Department, ProgressRecord, Lesson, QuizAttempt,
)
from app.schemas.patient_report import (
    PatientReportRowResponse, PatientReportResponse,
    PatientProgressResponse, PatientLessonProgressResponse,
)
from app.api.deps_admin import get_current_admin
from app.infrastructure.db.repositories.hospital_scoped_repository import ensure_hospital_access
from app.core.encryption import blind_index

router = APIRouter(prefix="/admin", tags=["admin_patient_report"])

STAGE_DISPLAY_NAMES = {
    "welcome": "خوش‌آمدگویی",
    "admission": "پذیرش در بخش",
    "procedure_intro": "آشنایی با عمل",
    "before_procedure": "قبل از عمل",
    "procedure": "حین عمل",
    "after_procedure": "بعد از عمل",
    "daily_inpatient": "آموزش روزانه‌ی بستری",
    "discharge": "ترخیص",
    "home_care": "مراقبت در منزل",
    "follow_up": "پیگیری",
    "long_term_monitoring": "پایش بلندمدت",
}


def _resolve_profile_hospital_id(db: Session, profile: PatientAccessProfile) -> uuid.UUID | None:
    if profile.hospital_id:
        return profile.hospital_id
    if profile.qr_access_point_id:
        qr = db.query(QRAccessPoint).filter(QRAccessPoint.id == profile.qr_access_point_id).first()
        return qr.hospital_id if qr else None
    return None


@router.get("/patient-report", response_model=PatientReportResponse)
async def get_patient_report(
    hospital_id: uuid.UUID,
    department_id: uuid.UUID | None = None,
    search: str | None = None,
    stage_code: str | None = None,
    limit: int = 100,
    offset: int = 0,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    ensure_hospital_access(admin, db, hospital_id)

    query = (
        db.query(PatientRegistration)
        .join(PatientAccessProfile, PatientRegistration.patient_access_profile_id == PatientAccessProfile.id)
        .outerjoin(QRAccessPoint, PatientAccessProfile.qr_access_point_id == QRAccessPoint.id)
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
        # national_id / phone_number are encrypted at rest, so ILIKE
        # can never match them - a plain substring search on
        # ciphertext is meaningless. If the term is all digits, treat
        # it as an exact national_id/phone_number lookup via the
        # one-way blind index instead (see encryption.py::blind_index).
        # Otherwise, fall back to a normal name search.
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

    total = query.count()

    registrations = (
        query.order_by(PatientRegistration.created_at.desc())
        .offset(offset)
        .limit(min(limit, 200))
        .all()
    )

    rows: list[PatientReportRowResponse] = []

    for reg in registrations:
        profile = reg.patient_access_profile

        if profile.hospital_id and profile.department_id:
            hospital = db.query(Hospital).filter(Hospital.id == profile.hospital_id).first()
            department = db.query(Department).filter(Department.id == profile.department_id).first()
        else:
            qr = db.query(QRAccessPoint).filter(QRAccessPoint.id == profile.qr_access_point_id).first()
            hospital = qr.hospital if qr else None
            department = qr.department if qr else None

        journey = (
            db.query(PatientJourneyProfile)
            .options(
                joinedload(PatientJourneyProfile.disease),
                joinedload(PatientJourneyProfile.treatment),
            )
            .filter(
                PatientJourneyProfile.patient_access_profile_id == profile.id,
                PatientJourneyProfile.is_active.is_(True),
            )
            .order_by(PatientJourneyProfile.created_at.desc())
            .first()
        )

        if stage_code and (not journey or journey.current_stage.value != stage_code):
            continue

        current_stage_value = journey.current_stage.value if journey else "welcome"

        rows.append(PatientReportRowResponse(
            patient_access_profile_id=profile.id,
            first_name=reg.first_name,
            last_name=reg.last_name,
            national_id=reg.national_id,
            phone_number=reg.phone_number,
            insurance_code=reg.insurance_code,
            hospital_name=hospital.name if hospital else "—",
            department_name=department.name if department else "—",
            disease_name=journey.disease.name if journey and journey.disease else None,
            treatment_name=journey.treatment.name if journey and journey.treatment else None,
            has_surgery=journey.has_surgery if journey else None,
            age=journey.age if journey else None,
            gender=journey.gender if journey else None,
            current_stage_code=current_stage_value,
            current_stage_name=STAGE_DISPLAY_NAMES.get(current_stage_value, current_stage_value),
            onboarding_completed=bool(journey and journey.onboarding_completed_at),
            registered_at=reg.created_at,
            last_seen_at=profile.last_seen_at,
        ))

    return PatientReportResponse(total=total, rows=rows)


@router.get("/patient-report/{patient_access_profile_id}/progress", response_model=PatientProgressResponse)
async def get_patient_progress(
    patient_access_profile_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    profile = db.query(PatientAccessProfile).filter(PatientAccessProfile.id == patient_access_profile_id).first()
    if not profile:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "بیمار پیدا نشد.")

    hospital_id = _resolve_profile_hospital_id(db, profile)
    if not hospital_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "بیمارستان این بیمار مشخص نیست.")

    ensure_hospital_access(admin, db, hospital_id)

    rows = (
        db.query(ProgressRecord, Lesson.title)
        .join(Lesson, ProgressRecord.lesson_id == Lesson.id)
        .filter(ProgressRecord.patient_access_profile_id == patient_access_profile_id)
        .order_by(ProgressRecord.updated_at.desc())
        .all()
    )

    lessons = [
        PatientLessonProgressResponse(
            lesson_id=pr.lesson_id,
            lesson_title=title,
            status=pr.status.value,
            started_at=pr.started_at,
            completed_at=pr.completed_at,
        )
        for pr, title in rows
    ]

    quiz_total = (
        db.query(func.count(QuizAttempt.id))
        .filter(QuizAttempt.patient_access_profile_id == patient_access_profile_id)
        .scalar()
    ) or 0
    quiz_correct = (
        db.query(func.count(QuizAttempt.id))
        .filter(
            QuizAttempt.patient_access_profile_id == patient_access_profile_id,
            QuizAttempt.is_correct.is_(True),
        )
        .scalar()
    ) or 0

    return PatientProgressResponse(
        total_lessons_viewed=len(lessons),
        total_lessons_completed=sum(1 for l in lessons if l.status == "completed"),
        quiz_total=quiz_total,
        quiz_correct=quiz_correct,
        lessons=lessons,
    )