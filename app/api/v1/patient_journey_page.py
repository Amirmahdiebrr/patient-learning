# app/api/v1/patient_journey_page.py
"""
app/api/v1/patient_journey_page.py

Patient-facing "مسیر درمان من" page: per-stage lesson-completion
progress bars, an overall progress bar, and the patient's quiz
attempt history (correct/incorrect per question).
"""

from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import PatientJourneyProfile
from app.api.deps import AccessContext, get_access_context, get_active_journey
from app.services.patient_progress_service import get_journey_progress, get_quiz_attempt_history
from app.core.templates import templates

router = APIRouter(tags=["patient_journey_page"])


@router.get("/my-journey")
async def my_journey_page(
    request: Request,
    context: AccessContext = Depends(get_access_context),
    journey: PatientJourneyProfile = Depends(get_active_journey),
    db: Session = Depends(get_db),
):
    if not journey.onboarding_completed_at:
        return RedirectResponse(url="/onboarding", status_code=303)

    department = context.department

    progress = get_journey_progress(
        db, journey,
        patient_access_profile_id=context.patient_profile.id,
        hospital_id=context.hospital_id,
        department_id=context.department_id,
        department_type_id=department.department_type_id,
    )

    quiz_history = get_quiz_attempt_history(db, context.patient_profile.id)

    return templates.TemplateResponse(
        request,
        "patient_my_journey.html",
        {
            "request": request,
            "progress": progress,
            "quiz_history": quiz_history,
            "hospital": context.hospital,
            "department": context.department,
        },
    )