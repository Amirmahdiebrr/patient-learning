# app/api/v1/patient_self_auth.py
"""
app/api/v1/patient_self_auth.py

Lets a patient register or log in directly from the panel, without
ever scanning a QR code. Registration collects identity, contact
info, hospital/department choice, and health/journey details
(disease/treatment/procedure) all in one form, then signs the same
PATIENT_PROFILE cookie the QR flow uses.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Request, Response, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.csrf import issue_csrf_cookie
from app.core.encryption import hash_lookup_value
from app.core.event_bus import event_bus
from app.core.events import PatientRegistered
from app.core.security import hash_password, verify_password
from app.core.templates import templates
from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import (
    Hospital, Department, Disease, Treatment, Procedure,
    PatientAccessProfile, PatientRegistration, PatientJourneyProfile, JourneyStageCode,
)
from app.schemas.admin import HospitalResponse, DepartmentResponse
from app.schemas.content_admin import ProcedureResponse
from app.schemas.patient import (
    PatientSelfRegisterRequest, PatientLoginRequest, PatientSelfAuthResponse, OnboardingOptionsResponse,
)
from app.services import access_gate_service
from app.services.content_admin.procedure_service import list_procedures
from app.api.deps_rate_limit import rate_limit

router = APIRouter(tags=["patient_self_auth"])

COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 180

REGISTER_RATE_LIMIT = 10
REGISTER_RATE_WINDOW_SECONDS = 3600
LOGIN_RATE_LIMIT = 15
LOGIN_RATE_WINDOW_SECONDS = 900


# ==========================
# HTML pages
# ==========================

@router.get("/login")
async def patient_login_page(request: Request):
    return templates.TemplateResponse(request, "patient_login.html", {"request": request})


@router.get("/register")
async def patient_register_page(request: Request):
    return templates.TemplateResponse(request, "patient_register.html", {"request": request})


# ==========================
# Public lookups for the registration form
# ==========================

@router.get("/patient-auth/hospitals", response_model=list[HospitalResponse])
async def list_public_hospitals(db: Session = Depends(get_db)):
    return db.query(Hospital).filter(Hospital.is_active.is_(True)).order_by(Hospital.name).all()


@router.get("/patient-auth/hospitals/{hospital_id}/departments", response_model=list[DepartmentResponse])
async def list_public_departments(hospital_id: uuid.UUID, db: Session = Depends(get_db)):
    departments = (
        db.query(Department)
        .filter(Department.hospital_id == hospital_id, Department.is_active.is_(True))
        .order_by(Department.name)
        .all()
    )
    return [
        DepartmentResponse(
            id=d.id, hospital_id=d.hospital_id, name=d.name, slug=d.slug, is_active=d.is_active,
            department_type_id=d.department_type_id,
            department_type_name=d.department_type.name if d.department_type else None,
        )
        for d in departments
    ]


@router.get("/patient-auth/procedures", response_model=list[ProcedureResponse])
async def list_public_procedures(department_type_id: uuid.UUID, db: Session = Depends(get_db)):
    procedures = list_procedures(db, department_type_id, include_inactive=False)
    return [
        ProcedureResponse(
            id=p.id, department_type_id=p.department_type_id, name=p.name,
            slug=p.slug, is_active=p.is_active, display_order=p.display_order,
        )
        for p in procedures
    ]


@router.get("/patient-auth/onboarding-options", response_model=OnboardingOptionsResponse)
async def public_onboarding_options(db: Session = Depends(get_db)):
    diseases = db.query(Disease).filter(Disease.is_active.is_(True)).order_by(Disease.name).all()
    treatments = db.query(Treatment).filter(Treatment.is_active.is_(True)).order_by(Treatment.name).all()

    treatments_by_disease: dict[str, list[dict]] = {}
    for t in treatments:
        treatments_by_disease.setdefault(str(t.disease_id), []).append({"id": str(t.id), "name": t.name})

    return OnboardingOptionsResponse(
        diseases=[{"id": str(d.id), "name": d.name} for d in diseases],
        treatments_by_disease=treatments_by_disease,
    )


# ==========================
# Register / Login / Logout
# ==========================

@router.post("/patient-auth/register", response_model=PatientSelfAuthResponse)
async def patient_self_register(
    payload: PatientSelfRegisterRequest,
    response: Response,
    db: Session = Depends(get_db),
    _rl=Depends(rate_limit("patient_self_register", REGISTER_RATE_LIMIT, REGISTER_RATE_WINDOW_SECONDS)),
):
    hospital = db.query(Hospital).filter(Hospital.id == payload.hospital_id, Hospital.is_active.is_(True)).first()
    if not hospital:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "بیمارستان پیدا نشد.")

    department = (
        db.query(Department)
        .filter(
            Department.id == payload.department_id,
            Department.hospital_id == payload.hospital_id,
            Department.is_active.is_(True),
        )
        .first()
    )
    if not department:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "بخش پیدا نشد یا به این بیمارستان تعلق ندارد.")

    if payload.procedure_id:
        procedure = db.query(Procedure).filter(Procedure.id == payload.procedure_id).first()
        if not procedure or procedure.department_type_id != department.department_type_id:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "این عمل متعلق به این بخش نیست.")

    national_id_hash = hash_lookup_value(payload.national_id)
    existing = db.query(PatientRegistration).filter(PatientRegistration.national_id_hash == national_id_hash).first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "این کد ملی قبلاً ثبت‌نام شده است. لطفاً وارد شوید.")

    profile = PatientAccessProfile(hospital_id=payload.hospital_id, department_id=payload.department_id)
    db.add(profile)
    db.flush()

    registration = PatientRegistration(
        patient_access_profile_id=profile.id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        national_id=payload.national_id,
        national_id_hash=national_id_hash,
        phone_number=payload.phone_number,
        phone_number_hash=hash_lookup_value(payload.phone_number),
        insurance_code=payload.insurance_code,
        password_hash=hash_password(payload.password),
    )
    db.add(registration)

    target_stage = JourneyStageCode.BEFORE_PROCEDURE if payload.has_surgery else JourneyStageCode.ADMISSION
    journey = PatientJourneyProfile(
        patient_access_profile_id=profile.id,
        disease_id=payload.disease_id,
        treatment_id=payload.treatment_id,
        procedure_id=payload.procedure_id,
        has_surgery=payload.has_surgery,
        age=payload.age,
        gender=payload.gender,
        current_stage=target_stage,
        onboarding_completed_at=datetime.utcnow(),
    )
    db.add(journey)

    db.commit()
    db.refresh(profile)

    response.set_cookie(
        key=settings.PATIENT_PROFILE_COOKIE_NAME,
        value=access_gate_service.sign_profile_cookie(profile.id),
        max_age=COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
    )
    issue_csrf_cookie(response, settings.CSRF_COOKIE_NAME)

    event_bus.publish(PatientRegistered(
        patient_access_profile_id=profile.id,
        hospital_id=payload.hospital_id,
        department_id=payload.department_id,
    ))

    return PatientSelfAuthResponse(redirect_url="/home")


@router.post("/patient-auth/login", response_model=PatientSelfAuthResponse)
async def patient_self_login(
    payload: PatientLoginRequest,
    response: Response,
    db: Session = Depends(get_db),
    _rl=Depends(rate_limit("patient_self_login", LOGIN_RATE_LIMIT, LOGIN_RATE_WINDOW_SECONDS)),
):
    national_id_hash = hash_lookup_value(payload.national_id)
    registration = db.query(PatientRegistration).filter(PatientRegistration.national_id_hash == national_id_hash).first()

    if not registration or not registration.password_hash or not verify_password(payload.password, registration.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "کد ملی یا رمز عبور اشتباه است.")

    profile = registration.patient_access_profile
    profile.last_seen_at = datetime.utcnow()
    db.commit()

    response.set_cookie(
        key=settings.PATIENT_PROFILE_COOKIE_NAME,
        value=access_gate_service.sign_profile_cookie(profile.id),
        max_age=COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
    )
    issue_csrf_cookie(response, settings.CSRF_COOKIE_NAME)

    return PatientSelfAuthResponse(redirect_url="/home")


@router.post("/patient-auth/logout")
async def patient_self_logout(response: Response):
    response.delete_cookie(settings.PATIENT_PROFILE_COOKIE_NAME)
    response.delete_cookie(settings.ACCESS_COOKIE_NAME)
    response.delete_cookie(settings.CSRF_COOKIE_NAME)
    return {"ok": True}