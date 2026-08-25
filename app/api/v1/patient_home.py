# app/api/v1/patient_home.py
"""
app/api/v1/patient_home.py

Patient's main screen: an ordered "journey" view of every stage up
to and including the patient's current stage, each stage carrying its
own lessons and its own stage-level quiz, with sequential
unlock/completion state. Redirects back to onboarding if not
completed yet.

Also passes patient_first_name for the personalized welcome hero at
the top of the page - always available by the time /home is reached,
since onboarding_completed_at is required to get past the redirect
below, and onboarding always creates the PatientRegistration row
first (see onboarding.py / patient_self_auth.py).
"""

from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import PatientJourneyProfile
from app.api.deps import AccessContext, get_access_context, get_active_journey
from app.services.content_targeting_service import get_journey_timeline
from app.core.templates import templates

router = APIRouter(tags=["patient_home"])


@router.get("/home")
async def patient_home(
    request: Request,
    context: AccessContext = Depends(get_access_context),
    journey: PatientJourneyProfile = Depends(get_active_journey),
    db: Session = Depends(get_db),
):
    if not journey.onboarding_completed_at:
        return RedirectResponse(url="/onboarding", status_code=303)

    department = context.department

    timeline = get_journey_timeline(
        db,
        journey,
        patient_access_profile_id=context.patient_profile.id,
        hospital_id=context.hospital_id,
        department_id=context.department_id,
        department_type_id=department.department_type_id,
    )

    registration = context.patient_profile.registration
    patient_first_name = registration.first_name if registration else None

    return templates.TemplateResponse(
        request,
        "patient_home.html",
        {
            "request": request,
            "timeline": timeline,
            "journey": journey,
            "hospital": context.hospital,
            "department": context.department,
            "patient_first_name": patient_first_name,
        },
    )