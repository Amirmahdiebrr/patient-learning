"""
app/api/v1/patient_home.py

Patient's main screen: lessons relevant to their current journey
stage + department type + condition, plus any stage-level quiz
questions for that same stage/department type. Redirects back to
onboarding if not completed yet.
"""

from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import PatientJourneyProfile
from app.api.deps import AccessContext, get_access_context, get_active_journey
from app.services.content_targeting_service import get_lessons_for_journey, get_stage_quiz_for_journey
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

    department = context.qr_access_point.department

    lessons = get_lessons_for_journey(
        db,
        journey,
        hospital_id=context.qr_access_point.hospital_id,
        department_id=context.qr_access_point.department_id,
        department_type_id=department.department_type_id,
    )

    stage_quiz_questions = get_stage_quiz_for_journey(
        db,
        journey,
        department_type_id=department.department_type_id,
    )

    return templates.TemplateResponse(
        request,
        "patient_home.html",
        {
            "request": request,
            "lessons": lessons,
            "stage_quiz_questions": stage_quiz_questions,
            "journey": journey,
            "hospital": context.qr_access_point.hospital,
            "department": department,
        },
    )