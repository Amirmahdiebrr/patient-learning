"""
app/api/v1/welcome.py

The very first screen a patient sees right after scanning the QR,
before onboarding. Shows published lessons tagged for the WELCOME
journey stage, then lets the patient move on to onboarding. The
transition to ADMISSION goes through the journey state machine.
"""

from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

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

    department = context.qr_access_point.department

    lessons = get_lessons_for_journey(
        db,
        journey,
        hospital_id=context.qr_access_point.hospital_id,
        department_id=context.qr_access_point.department_id,
        department_type_id=department.department_type_id,
    )

    return templates.TemplateResponse(
        request,
        "welcome.html",
        {
            "request": request,
            "lessons": lessons,
            "hospital": context.qr_access_point.hospital,
            "department": department,
        },
    )


@router.post("/welcome/continue")
async def welcome_continue(
    context: AccessContext = Depends(get_access_context),
    journey: PatientJourneyProfile = Depends(get_active_journey),
    db: Session = Depends(get_db),
):
    try:
        transition_stage(
            db, journey, JourneyStageCode.ADMISSION,
            hospital_id=context.qr_access_point.hospital_id,
            triggered_by="automatic",
        )
    except InvalidStageTransitionError:
        pass

    return RedirectResponse(url="/onboarding", status_code=303)