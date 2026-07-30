"""
app/api/v1/entry.py

The route embedded inside every printed QR code:
    https://{APP_BASE_URL}/entry?token=<qr_access_point.access_token>

Resolves the token, issues the signed access + profile cookies, and
redirects into the app. This is the ONLY legitimate way to obtain a
valid access cookie - there is no username/password login for
patients.
"""

from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import PatientJourneyProfile
from app.services import access_gate_service
from app.core.templates import templates

router = APIRouter(tags=["entry"])

# itsdangerous signatures never expire by default (max_age=None on verify),
# but the cookie itself still needs a browser-side max_age so it doesn't
# live forever on a shared/public device. 180 days matches a realistic
# "in case the patient revisits after discharge" window.
COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 180


@router.get("/entry")
async def qr_entry(request: Request, token: str, db: Session = Depends(get_db)):

    access_point = access_gate_service.resolve_active_qr_access_point(db, token)

    if not access_point:
        return RedirectResponse(url="/invalid-qr", status_code=303)

    existing_profile_id = access_gate_service.verify_profile_cookie(
        request.cookies.get(settings.PATIENT_PROFILE_COOKIE_NAME)
    )

    patient_profile = access_gate_service.get_or_create_patient_profile(
        db,
        qr_access_point_id=access_point.id,
        existing_profile_id=existing_profile_id,
    )

    journey = (
        db.query(PatientJourneyProfile)
        .filter(
            PatientJourneyProfile.patient_access_profile_id == patient_profile.id,
            PatientJourneyProfile.is_active.is_(True),
        )
        .order_by(PatientJourneyProfile.created_at.desc())
        .first()
    )

    destination = "/onboarding" if not journey or not journey.onboarding_completed_at else "/home"

    response = RedirectResponse(url=destination, status_code=303)

    response.set_cookie(
        key=settings.ACCESS_COOKIE_NAME,
        value=access_gate_service.sign_access_cookie(access_point.id),
        max_age=COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
    )
    response.set_cookie(
        key=settings.PATIENT_PROFILE_COOKIE_NAME,
        value=access_gate_service.sign_profile_cookie(patient_profile.id),
        max_age=COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
    )

    return response


@router.get("/invalid-qr")
async def invalid_qr(request: Request):
    return templates.TemplateResponse(
        request, "invalid_qr.html", {"request": request}, status_code=400
    )