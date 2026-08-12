"""
app/api/v1/admin_patient_report.py

Admin-only read report of registered patients: identity/contact info
(PatientRegistration) joined with their current journey stage/health
routing info (PatientJourneyProfile) and which hospital/department
they registered through (via their QRAccessPoint). Scoped by
hospital/department like other admin endpoints - a hospital_admin or
department_admin only sees patients registered under their scope;
super_admin sees everyone.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import (
    AdminUser, PatientRegistration, PatientAccessProfile, PatientJourneyProfile,
    QRAccessPoint, Hospital, Department,
)
from app.schemas.patient_report import PatientReportRowResponse, PatientReportResponse
from app.api.deps_admin import get_current_admin
from app.infrastructure.db.repositories.hospital_scoped_repository import ensure_hospital_access
from app.core.encryption import blind_index

router = APIRouter(prefix="/admin", tags=["admin_patient_report"])


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
        .join(QRAccessPoint, PatientAccessProfile.qr_access_point_id == QRAccessPoint.id)
        .join(Hospital, QRAccessPoint.hospital_id == Hospital.id)
        .join(Department, QRAccessPoint.department_id == Department.id)
        .options(
            joinedload(PatientRegistration.patient_access_profile)
            .joinedload(PatientAccessProfile.qr_access_point)
            .joinedload(QRAccessPoint.hospital),
            joinedload(PatientRegistration.patient_access_profile)
            .joinedload(PatientAccessProfile.qr_access_point)
            .joinedload(QRAccessPoint.department),
        )
        .filter(QRAccessPoint.hospital_id == hospital_id)
    )

    if department_id:
        query = query.filter(QRAccessPoint.department_id == department_id)

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
        access_point = profile.qr_access_point

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

        stage_display_names = {
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

        rows.append(PatientReportRowResponse(
            patient_access_profile_id=profile.id,
            first_name=reg.first_name,
            last_name=reg.last_name,
            national_id=reg.national_id,
            phone_number=reg.phone_number,
            insurance_code=reg.insurance_code,
            hospital_name=access_point.hospital.name,
            department_name=access_point.department.name,
            disease_name=journey.disease.name if journey and journey.disease else None,
            treatment_name=journey.treatment.name if journey and journey.treatment else None,
            has_surgery=journey.has_surgery if journey else None,
            age=journey.age if journey else None,
            gender=journey.gender if journey else None,
            current_stage_code=journey.current_stage.value if journey else "welcome",
            current_stage_name=stage_display_names.get(journey.current_stage.value if journey else "welcome", ""),
            onboarding_completed=bool(journey and journey.onboarding_completed_at),
            registered_at=reg.created_at,
            last_seen_at=profile.last_seen_at,
        ))

    return PatientReportResponse(total=total, rows=rows)