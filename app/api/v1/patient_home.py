# app/api/v1/patient_home.py
"""
app/api/v1/patient_home.py

Patient's main screen: an ordered "journey" view of every stage up
to and including the patient's current stage, each stage carrying its
own lessons and its own stage-level quiz, with sequential
unlock/completion state. Redirects back to onboarding if not
completed yet.

The generic, hospital-wide WELCOME lesson (media + body, no
department_type_id) is shown as a one-time, dismissible hero at the
top of this page the very first time a patient reaches the
educational area - tracked via
PatientAccessProfile.general_welcome_acknowledged_at, separate from
hospital_welcome_acknowledged_at (the earlier, pre-onboarding
/welcome page). Once dismissed via POST /home/acknowledge-welcome, it
never appears again for that patient. This lesson is deliberately
excluded from the stage timeline itself (see
content_targeting_service.get_journey_timeline) - only a
department-specific WELCOME lesson, if one exists, shows there.

Surgery-related education (آشنایی با عمل / قبل از عمل / بعد از عمل)
is NOT rendered on this page at all - it lives on the dedicated
/my-surgery-education page, reached via the separate surgery sub-nav
(see app/templates/patient_surgery_subnav.html and
app/api/v1/patient_procedures.py).

The overall/current-stage progress figures used by the redesigned
hero stat cards are derived purely from the already-computed
`timeline` list - no extra queries, no change to the underlying
journey/progress data model.
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
from app.services.content_targeting_service import get_journey_timeline, get_lessons_for_stage
from app.core.templates import templates

router = APIRouter(tags=["patient_home"])


def _get_general_welcome_lesson(db: Session, journey: PatientJourneyProfile, context: AccessContext):
    lessons = get_lessons_for_stage(
        db, journey, JourneyStageCode.WELCOME,
        hospital_id=context.hospital_id,
        department_id=context.department_id,
        department_type_id=None,
    )
    return lessons[0] if lessons else None


def _compute_home_stats(timeline: list[dict]) -> dict:
    total_lessons = 0
    total_completed = 0
    current_stage_name = ""
    current_stage_lesson_count = 0
    current_stage_percent = 0
    next_lesson_id = None

    for stage in timeline:
        stage_lessons = stage["lessons"]
        total_lessons += len(stage_lessons)
        total_completed += sum(1 for l in stage_lessons if l["is_completed"])

        if stage["is_current"]:
            current_stage_name = stage["stage_name"]
            current_stage_lesson_count = len(stage_lessons)
            if current_stage_lesson_count:
                completed_here = sum(1 for l in stage_lessons if l["is_completed"])
                current_stage_percent = round((completed_here / current_stage_lesson_count) * 100)
            first_incomplete = next((l for l in stage_lessons if not l["is_completed"]), None)
            if first_incomplete:
                next_lesson_id = first_incomplete["lesson"].id

    overall_progress_percent = round((total_completed / total_lessons) * 100) if total_lessons else 0

    return {
        "overall_progress_percent": overall_progress_percent,
        "current_stage_name": current_stage_name,
        "current_stage_lesson_count": current_stage_lesson_count,
        "current_stage_percent": current_stage_percent,
        "next_lesson_id": next_lesson_id,
    }


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

    home_stats = _compute_home_stats(timeline)

    registration = context.patient_profile.registration
    patient_first_name = registration.first_name if registration else None

    show_general_welcome = not context.patient_profile.general_welcome_acknowledged_at
    general_welcome_lesson = _get_general_welcome_lesson(db, journey, context) if show_general_welcome else None

    csrf_token = request.cookies.get(settings.CSRF_COOKIE_NAME)

    response = templates.TemplateResponse(
        request,
        "patient_home.html",
        {
            "request": request,
            "timeline": timeline,
            "journey": journey,
            "hospital": context.hospital,
            "department": context.department,
            "patient_first_name": patient_first_name,
            "general_welcome_lesson": general_welcome_lesson if show_general_welcome else None,
            "csrf_token": csrf_token,
            **home_stats,
        },
    )

    if not csrf_token:
        issue_csrf_cookie(response, settings.CSRF_COOKIE_NAME)

    return response


@router.post("/home/acknowledge-welcome")
async def acknowledge_general_welcome(
    request: Request,
    csrf_token: str = Form(...),
    context: AccessContext = Depends(get_access_context),
    db: Session = Depends(get_db),
):
    verify_csrf(request, settings.CSRF_COOKIE_NAME, csrf_token)

    context.patient_profile.general_welcome_acknowledged_at = datetime.utcnow()
    db.commit()

    return RedirectResponse(url="/home", status_code=303)