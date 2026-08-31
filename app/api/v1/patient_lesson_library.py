# app/api/v1/patient_lesson_library.py
"""
app/api/v1/patient_lesson_library.py

Patient-facing lesson library: a searchable/filterable list of every
lesson currently accessible to the patient - every lesson inside an
UNLOCKED main-journey stage (see content_targeting_service.get_journey_timeline)
plus every lesson under the always-optional surgery-education section
(see content_targeting_service.get_surgery_education_groups). Locked
future-stage lessons are deliberately excluded.

Filtering (search text, stage, content type) happens server-side on
the already-resolved, already-authorized list - no new content
resolution logic.
"""

from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session

from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import PatientJourneyProfile
from app.api.deps import AccessContext, get_access_context, get_active_journey
from app.services.content_targeting_service import get_patient_lesson_library
from app.core.templates import templates

router = APIRouter(tags=["patient_lesson_library"])


@router.get("/my-lessons")
async def my_lesson_library(
    request: Request,
    q: str | None = None,
    stage: str | None = None,
    content_type: str | None = None,
    context: AccessContext = Depends(get_access_context),
    journey: PatientJourneyProfile = Depends(get_active_journey),
    db: Session = Depends(get_db),
):
    department = context.department

    library = get_patient_lesson_library(
        db, journey,
        patient_access_profile_id=context.patient_profile.id,
        hospital_id=context.hospital_id,
        department_id=context.department_id,
        department_type_id=department.department_type_id,
    )

    stage_options = []
    seen_stage_codes = set()
    for item in library:
        if item["stage_code"] not in seen_stage_codes:
            seen_stage_codes.add(item["stage_code"])
            stage_options.append({"code": item["stage_code"], "name": item["stage_name"]})

    filtered = library
    if q and q.strip():
        term = q.strip()
        filtered = [item for item in filtered if term in item["lesson"].title]
    if stage:
        filtered = [item for item in filtered if item["stage_code"] == stage]
    if content_type:
        if content_type == "quiz":
            filtered = [item for item in filtered if item["has_quiz"]]
        else:
            filtered = [item for item in filtered if content_type in item["media_types"]]

    return templates.TemplateResponse(
        request,
        "patient_lesson_library.html",
        {
            "request": request,
            "items": filtered,
            "stage_options": stage_options,
            "q": q or "",
            "selected_stage": stage or "",
            "selected_content_type": content_type or "",
        },
    )