# app/api/v1/welcome.py
"""
app/api/v1/welcome.py

The hospital-level welcome page. Deliberately generic - hospital
only, no department content - and shown EXACTLY ONCE per patient:
right after their very first entry (QR scan, before onboarding) or
right after self-service registration (patient_self_auth.py redirects
here instead of /home for that one call). Never shown again on any
later visit or login, tracked via
PatientAccessProfile.hospital_welcome_acknowledged_at - deliberately
NOT the same signal as onboarding_completed_at, since self-service
patients set that at registration time itself.

Department-specific welcome content lives on the /home hero instead
(see patient_home.py / patient_home.html).
"""

from datetime import datetime

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.csrf import verify_csrf, issue_csrf_cookie
from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import PatientJourneyProfile, JourneyStageCode
from app.api.deps import AccessContext, get_access_context, get_active_journey
from app.services.content_targeting_service import get_lessons_for_stage
from app.services.patient_journey_state_machine import transition_stage, InvalidStageTransitionError
from app.core.templates import templates

router = APIRouter(tags=["welcome"])


@router.get("/welcome")
async def welcome_page(
    request: Request,
    context: AccessContext = Depends(get_access_context),
    journey: PatientJourneyProfile = Depends(get_active_journey),
    db: Session = Depends(get_db),
):
    if context.patient_profile.hospital_welcome_acknowledged_at:
        return RedirectResponse(url="/home", status_code=303)

    department = context.department

    # Always the WELCOME-stage content specifically - not
    # journey.current_stage - because a self-service patient's
    # current_stage is already past WELCOME (set at registration), but
    # this page is still the same generic hospital-level content every
    # patient sees exactly once, regardless of which stage they've
    # already been routed to.
    lessons = get_lessons_for_stage(
        db, journey, JourneyStageCode.WELCOME,
        hospital_id=context.hospital_id,
        department_id=context.department_id,
        department_type_id=department.department_type_id,
    )

    csrf_token = request.cookies.get(settings.CSRF_COOKIE_NAME)

    response = templates.TemplateResponse(
        request,
        "welcome.html",
        {
            "request": request,
            "lessons": lessons,
            "hospital": context.hospital,
            "department": department,
            "csrf_token": csrf_token,
        },
    )

    if not csrf_token:
        issue_csrf_cookie(response, settings.CSRF_COOKIE_NAME)

    return response


@router.post("/welcome/continue")
async def welcome_continue(
    request: Request,
    csrf_token: str = Form(...),
    context: AccessContext = Depends(get_access_context),
    journey: PatientJourneyProfile = Depends(get_active_journey),
    db: Session = Depends(get_db),
):
    verify_csrf(request, settings.CSRF_COOKIE_NAME, csrf_token)

    context.patient_profile.hospital_welcome_acknowledged_at = datetime.utcnow()
    db.commit()

    if journey.onboarding_completed_at:
        # Self-service patient - onboarding data was already collected
        # at registration time, nothing left to fill in. Straight to
        # their department's lesson menu.
        return RedirectResponse(url="/home", status_code=303)

    try:
        transition_stage(
            db, journey, JourneyStageCode.ADMISSION,
            hospital_id=context.hospital_id,
            triggered_by="automatic",
        )
    except InvalidStageTransitionError:
        pass

    return RedirectResponse(url="/onboarding", status_code=303)