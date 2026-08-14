# app/api/v1/onboarding.py
"""
app/api/v1/onboarding.py

Used by the QR flow (patient already has a profile bound to a
hospital/department via QR or self-service registration, but still
needs to fill in identity + health details). Self-service patients
skip this entirely since /patient-auth/register collects everything
up front.
"""

from datetime import datetime

from fastapi import APIRouter, Request, Depends, Form, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.event_bus import event_bus
from app.core.events import PatientRegistered
from app.core.encryption import hash_lookup_value
from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import (
    Disease, Treatment, PatientJourneyProfile, JourneyStageCode, PatientRegistration,
)
from app.api.deps import AccessContext, get_access_context, get_active_journey
from app.services.patient_journey_state_machine import transition_stage, InvalidStageTransitionError
from app.core.templates import templates

router = APIRouter(tags=["onboarding"])

import re
NATIONAL_ID_PATTERN = re.compile(r"^\d{10}$")
PHONE_PATTERN = re.compile(r"^09\d{9}$")


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
            "department": context.department,
            "hospital": context.hospital,
        },
    )


@router.post("/onboarding")
async def onboarding_submit(
    request: Request,
    first_name: str = Form(...),
    last_name: str = Form(...),
    national_id: str = Form(...),
    phone_number: str = Form(...),
    insurance_code: str = Form(None),
    disease_id: str = Form(None),
    treatment_id: str = Form(None),
    has_surgery: str = Form(None),
    age: str = Form(None),
    gender: str = Form(None),
    context: AccessContext = Depends(get_access_context),
    journey: PatientJourneyProfile = Depends(get_active_journey),
    db: Session = Depends(get_db),
):
    first_name = first_name.strip()
    last_name = last_name.strip()
    national_id = national_id.strip()
    phone_number = phone_number.strip()

    if not NATIONAL_ID_PATTERN.match(national_id):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "کد ملی نامعتبر است.")
    if not PHONE_PATTERN.match(phone_number):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "شماره همراه نامعتبر است.")

    registration = (
        db.query(PatientRegistration)
        .filter(PatientRegistration.patient_access_profile_id == context.patient_profile.id)
        .first()
    )
    if not registration:
        registration = PatientRegistration(patient_access_profile_id=context.patient_profile.id)
        db.add(registration)

    registration.first_name = first_name
    registration.last_name = last_name
    registration.national_id = national_id
    registration.national_id_hash = hash_lookup_value(national_id)
    registration.phone_number = phone_number
    registration.phone_number_hash = hash_lookup_value(phone_number)
    registration.insurance_code = insurance_code.strip() if insurance_code else None

    journey.disease_id = disease_id or None
    journey.treatment_id = treatment_id or None
    journey.has_surgery = {"yes": True, "no": False}.get(has_surgery)
    journey.age = int(age) if age and age.isdigit() else None
    journey.gender = gender if gender in ("male", "female", "other") else None
    journey.onboarding_completed_at = datetime.utcnow()

    db.commit()

    target_stage = JourneyStageCode.BEFORE_PROCEDURE if journey.has_surgery else JourneyStageCode.ADMISSION

    try:
        transition_stage(
            db, journey, target_stage,
            hospital_id=context.hospital_id,
            triggered_by="automatic",
        )
    except InvalidStageTransitionError:
        pass

    event_bus.publish(PatientRegistered(
        patient_access_profile_id=context.patient_profile.id,
        hospital_id=context.hospital_id,
        department_id=context.department_id,
    ))

    return RedirectResponse(url="/home", status_code=303)