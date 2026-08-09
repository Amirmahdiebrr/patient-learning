"""
app/api/v1/entry.py

The route embedded inside every printed QR code:
    https://{APP_BASE_URL}/entry?token=<qr_access_point.access_token>

Resolves the token, issues the signed access + profile cookies, and
redirects into the app. This is the ONLY legitimate way to obtain a
valid access cookie - there is no username/password login for
patients. Rate-limited by IP to slow down brute-force guessing of QR
tokens. Publishes a QRScanned domain event on every successful scan.
"""

from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.event_bus import event_bus
from app.core.events import QRScanned
from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import PatientJourneyProfile
from app.services import access_gate_service
from app.core.templates import templates
from app.api.deps_rate_limit import rate_limit

router = APIRouter(tags=["entry"])

# itsdangerous signatures never expire by default (max_age=None on verify),
# but the cookie itself still needs a browser-side max_age so it doesn't
# live forever on a shared/public device. 180 days matches a realistic
# "in case the patient revisits after discharge" window.
COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 180

ENTRY_RATE_LIMIT = 30
ENTRY_RATE_WINDOW_SECONDS = 300


@router.get("/entry")
async def qr_entry(
    request: Request,
    token: str,
    db: Session = Depends(get_db),
    _rate_limit=Depends(rate_limit("entry", ENTRY_RATE_LIMIT, ENTRY_RATE_WINDOW_SECONDS)),
):

    access_point = access_gate_service.resolve_active_qr_access_point(db, token)

    if not access_point:
        return RedirectResponse(url="/invalid-qr", status_code=303)

    existing_profile_id = access_gate_service.verify_profile_cookie(
        request.cookies.get(settings.PATIENT_PROFILE_COOKIE_NAME)
    )

    was_existing_profile = existing_profile_id is not None

    patient_profile = access_gate_service.get_or_create_patient_profile(
        db,
        qr_access_point_id=access_point.id,
        existing_profile_id=existing_profile_id,
    )

    event_bus.publish(QRScanned(
        qr_access_point_id=access_point.id,
        patient_access_profile_id=patient_profile.id,
        hospital_id=access_point.hospital_id,
        department_id=access_point.department_id,
        is_new_profile=not was_existing_profile,
    ))

    journey = (
        db.query(PatientJourneyProfile)
        .filter(
            PatientJourneyProfile.patient_access_profile_id == patient_profile.id,
            PatientJourneyProfile.is_active.is_(True),
        )
        .order_by(PatientJourneyProfile.created_at.desc())
        .first()
    )

    if not journey:
        destination = "/welcome"
    elif not journey.onboarding_completed_at:
        destination = "/welcome" if journey.current_stage.value == "welcome" else "/onboarding"
    else:
        destination = "/home"

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