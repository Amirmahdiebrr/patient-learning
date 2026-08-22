# app/api/v1/onboarding.py
"""
app/api/v1/onboarding.py

Used by the QR flow. Self-service patients skip this since
/patient-auth/register collects everything up front.
"""

import re
import uuid
from datetime import datetime

from fastapi import APIRouter, Request, Depends, Form, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.event_bus import event_bus
from app.core.events import PatientRegistered
from app.core.encryption import hash_lookup_value
from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import (
    Disease, Treatment, Procedure, PatientJourneyProfile, JourneyStageCode, PatientRegistration,
)
from app.api.deps import AccessContext, get_access_context, get_active_journey
from app.services.patient_journey_state_machine import transition_stage, InvalidStageTransitionError
from app.core.templates import templates

router = APIRouter(tags=["onboarding"])

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
            "department_type_id": context.department.department_type_id,
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
    procedure_id: str = Form(None),
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

    resolved_procedure_id = None
    if procedure_id:
        try:
            candidate = uuid.UUID(procedure_id)
        except ValueError:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "شناسه‌ی عمل نامعتبر است.")
        # عمل انتخابی باید حتماً متعلق به همان نوع بخشی باشد که بیمار
        # در آن بستری است - این همان محدودیتی است که تضمین می‌کند
        # بیمار فقط می‌تواند از بین اعمال مخصوص بخش خودش انتخاب کند.
        procedure = db.query(Procedure).filter(Procedure.id == candidate).first()
        if not procedure or procedure.department_type_id != context.department.department_type_id:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "این عمل متعلق به این بخش نیست.")
        resolved_procedure_id = candidate

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
    journey.procedure_id = resolved_procedure_id
    journey.has_surgery = {"yes": True, "no": False}.get(has_surgery)
    journey.age = int(age) if age and age.isdigit() else None
    journey.gender = gender if gender in ("male", "female", "other") else None
    journey.onboarding_completed_at = datetime.utcnow()

    db.commit()

    # بیمارانی که قرار است عمل جراحی داشته باشند، اول وارد «آشنایی با
    # عمل» می‌شوند (محتوای مخصوص همان عملی که بالا انتخاب کردند) و
    # بعد از آن به «قبل از عمل» می‌روند - نه مستقیم.
    target_stage = JourneyStageCode.PROCEDURE_INTRO if journey.has_surgery else JourneyStageCode.ADMISSION

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