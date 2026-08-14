# app/api/v1/welcome.py
"""
app/api/v1/welcome.py
"""

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.csrf import verify_csrf, issue_csrf_cookie
from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import PatientJourneyProfile, JourneyStageCode
from app.api.deps import AccessContext, get_access_context, get_active_journey
from app.services.content_targeting_service import get_lessons_for_journey
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
    if journey.onboarding_completed_at:
        return RedirectResponse(url="/home", status_code=303)

    department = context.department

    lessons = get_lessons_for_journey(
        db,
        journey,
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

    try:
        transition_stage(
            db, journey, JourneyStageCode.ADMISSION,
            hospital_id=context.hospital_id,
            triggered_by="automatic",
        )
    except InvalidStageTransitionError:
        pass

    return RedirectResponse(url="/onboarding", status_code=303)