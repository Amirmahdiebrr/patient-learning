"""
app/api/deps.py

FastAPI dependencies shared across patient-facing routers.
"""

from dataclasses import dataclass
import uuid

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AccessGateError
from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import QRAccessPoint, PatientAccessProfile, PatientJourneyProfile
from app.services import access_gate_service


@dataclass
class AccessContext:
    qr_access_point: QRAccessPoint
    patient_profile: PatientAccessProfile


def get_access_context(request: Request, db: Session = Depends(get_db)) -> AccessContext:
    """
    Enforces the QR-only access gate. Raises AccessGateError (caught
    by a global exception handler) if the request doesn't carry a
    valid, signed access cookie proving a QR was scanned.
    """
    access_cookie = request.cookies.get(settings.ACCESS_COOKIE_NAME)
    qr_access_point_id = access_gate_service.verify_access_cookie(access_cookie)

    if not qr_access_point_id:
        raise AccessGateError("missing_or_invalid_access_cookie")

    qr_access_point = (
        db.query(QRAccessPoint)
        .filter(QRAccessPoint.id == qr_access_point_id)
        .first()
    )

    if not qr_access_point or qr_access_point.status.value != "active":
        raise AccessGateError("access_point_revoked_or_missing")

    profile_cookie = request.cookies.get(settings.PATIENT_PROFILE_COOKIE_NAME)
    profile_id = access_gate_service.verify_profile_cookie(profile_cookie)

    patient_profile = None
    if profile_id:
        patient_profile = (
            db.query(PatientAccessProfile)
            .filter(PatientAccessProfile.id == profile_id)
            .first()
        )

    if not patient_profile:
        # Should not normally happen (entry endpoint always sets both
        # cookies together), but fail closed rather than silently
        # creating a new profile mid-session.
        raise AccessGateError("missing_patient_profile")

    return AccessContext(qr_access_point=qr_access_point, patient_profile=patient_profile)


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