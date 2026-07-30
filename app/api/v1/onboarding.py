"""
app/api/v1/onboarding.py

Onboarding questionnaire shown right after a QR scan. Collects the
minimum data needed to route educational content (disease, treatment/
surgery flag, age, gender) - no name, no national ID, no PII.
"""

from datetime import datetime

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import Disease, Treatment, PatientJourneyProfile, JourneyStageCode
from app.api.deps import AccessContext, get_access_context, get_active_journey
from app.core.templates import templates

router = APIRouter(tags=["onboarding"])


@router.get("/onboarding")
async def onboarding_form(
    request: Request,
    context: AccessContext = Depends(get_access_context),
    journey: PatientJourneyProfile = Depends(get_active_journey),
    db: Session = Depends(get_db),
):
    diseases = db.query(Disease).filter(Disease.is_active.is_(True)).order_by(Disease.name).all()
    treatments = db.query(Treatment).filter(Treatment.is_active.is_(True)).order_by(Treatment.name).all()

    return templates.TemplateResponse(
        request,
        "onboarding.html",
        {
            "request": request,
            "diseases": diseases,
            "treatments": treatments,
            "department": context.qr_access_point.department,
            "hospital": context.qr_access_point.hospital,
        },
    )


@router.post("/onboarding")
async def onboarding_submit(
    request: Request,
    disease_id: str = Form(None),
    treatment_id: str = Form(None),
    has_surgery: str = Form(None),  # "yes" | "no" | None
    age: str = Form(None),
    gender: str = Form(None),
    context: AccessContext = Depends(get_access_context),
    journey: PatientJourneyProfile = Depends(get_active_journey),
    db: Session = Depends(get_db),
):
    journey.disease_id = disease_id or None
    journey.treatment_id = treatment_id or None
    journey.has_surgery = {"yes": True, "no": False}.get(has_surgery)
    journey.age = int(age) if age and age.isdigit() else None
    journey.gender = gender if gender in ("male", "female", "other") else None

    journey.current_stage = (
        JourneyStageCode.BEFORE_PROCEDURE if journey.has_surgery else JourneyStageCode.ADMISSION
    )
    journey.onboarding_completed_at = datetime.utcnow()

    db.commit()

    return RedirectResponse(url="/home", status_code=303)