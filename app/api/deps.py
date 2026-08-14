# app/api/deps.py
"""
app/api/deps.py

FastAPI dependencies shared across patient-facing routers. Also
populates the per-request logging context (hospital_id,
department_id, patient_id) as soon as the access gate resolves them,
so every log line emitted for the rest of this request automatically
carries that context.

get_access_context now supports TWO ways a browser can prove it's an
authenticated patient:
  1. QR flow: PATIENT_PROFILE_COOKIE is set (issued at /entry), and
     the profile's qr_access_point_id points at an active
     QRAccessPoint - hospital/department are resolved from that QR.
  2. Self-service flow: PATIENT_PROFILE_COOKIE is set (issued at
     /patient-auth/register or /patient-auth/login), and the
     profile's hospital_id/department_id are set directly.
In both cases the only hard requirement is a valid, signed profile
cookie - the QR access cookie is no longer mandatory, since a
self-service patient never receives one.
"""

from dataclasses import dataclass
import uuid

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AccessGateError
from app.core.request_context import hospital_id_var, department_id_var, patient_id_var
from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import (
    QRAccessPoint, PatientAccessProfile, PatientJourneyProfile, Hospital, Department,
)
from app.services import access_gate_service


@dataclass
class AccessContext:
    patient_profile: PatientAccessProfile
    hospital: Hospital
    department: Department
    qr_access_point: QRAccessPoint | None = None

    @property
    def hospital_id(self) -> uuid.UUID:
        return self.hospital.id

    @property
    def department_id(self) -> uuid.UUID:
        return self.department.id


def get_access_context(request: Request, db: Session = Depends(get_db)) -> AccessContext:
    """
    Enforces the patient access gate. Raises AccessGateError (caught
    by a global exception handler) if the request doesn't carry a
    valid, signed patient-profile cookie, or if the hospital/
    department behind that profile can no longer be resolved.
    """
    profile_cookie = request.cookies.get(settings.PATIENT_PROFILE_COOKIE_NAME)
    profile_id = access_gate_service.verify_profile_cookie(profile_cookie)

    if not profile_id:
        raise AccessGateError("missing_or_invalid_profile_cookie")

    patient_profile = (
        db.query(PatientAccessProfile)
        .filter(PatientAccessProfile.id == profile_id)
        .first()
    )
    if not patient_profile:
        raise AccessGateError("missing_patient_profile")

    qr_access_point = None
    if patient_profile.qr_access_point_id:
        qr_access_point = (
            db.query(QRAccessPoint)
            .filter(
                QRAccessPoint.id == patient_profile.qr_access_point_id,
                QRAccessPoint.status.value == "active" if False else True,
            )
            .first()
        )
        if not qr_access_point or qr_access_point.status.value != "active":
            raise AccessGateError("access_point_revoked_or_missing")

    hospital_id = patient_profile.hospital_id or (qr_access_point.hospital_id if qr_access_point else None)
    department_id = patient_profile.department_id or (qr_access_point.department_id if qr_access_point else None)

    if not hospital_id or not department_id:
        raise AccessGateError("incomplete_access_context")

    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    department = db.query(Department).filter(Department.id == department_id).first()

    if not hospital or not department:
        raise AccessGateError("hospital_or_department_missing")

    hospital_id_var.set(str(hospital.id))
    department_id_var.set(str(department.id))
    patient_id_var.set(str(patient_profile.id))

    return AccessContext(
        patient_profile=patient_profile,
        hospital=hospital,
        department=department,
        qr_access_point=qr_access_point,
    )


def get_active_journey(
    context: AccessContext = Depends(get_access_context),
    db: Session = Depends(get_db),
) -> PatientJourneyProfile:
    """
    Returns the patient's active journey profile. Callers that require
    onboarding to be completed should check `onboarding_completed_at`
    themselves and redirect to /onboarding if it's None.
    """
    journey = (
        db.query(PatientJourneyProfile)
        .filter(
            PatientJourneyProfile.patient_access_profile_id == context.patient_profile.id,
            PatientJourneyProfile.is_active.is_(True),
        )
        .order_by(PatientJourneyProfile.created_at.desc())
        .first()
    )

    if not journey:
        journey = PatientJourneyProfile(
            patient_access_profile_id=context.patient_profile.id,
        )
        db.add(journey)
        db.commit()
        db.refresh(journey)

    return journey