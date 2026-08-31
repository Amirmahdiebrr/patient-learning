# app/api/v1/patient_procedures.py
# app/api/v1/patient_procedures.py
"""
app/api/v1/patient_procedures.py

Lets a patient see and change, at any time from their own page, which
procedure(s) apply to them within their department - not just once
at onboarding. Their before/after-procedure education (and stage
quiz) is then resolved as the union of content scoped to whichever
procedures they've selected - see content_targeting_service.py.

/my-surgery-education renders the always-optional "آشنایی با عمل /
قبل از عمل / بعد از عمل" groups - reached via the separate surgery
sub-nav (app/templates/patient_surgery_subnav.html), never part of
the locked main timeline on /home.
"""

import uuid

from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import PatientJourneyProfile
from app.api.deps import AccessContext, get_access_context, get_active_journey
from app.services import patient_procedure_service
from app.services.content_admin.procedure_service import list_procedures
from app.services.content_targeting_service import get_surgery_education_groups
from app.core.templates import templates

router = APIRouter(tags=["patient_procedures"])


class ProcedureOptionResponse(BaseModel):
    id: uuid.UUID
    name: str
    is_selected: bool


class ProcedureSelectionUpdateRequest(BaseModel):
    procedure_ids: list[uuid.UUID]


@router.get("/my-procedures")
async def my_procedures_page(
    request: Request,
    context: AccessContext = Depends(get_access_context),
    journey: PatientJourneyProfile = Depends(get_active_journey),
):
    return templates.TemplateResponse(
        request,
        "patient_procedures.html",
        {
            "request": request,
            "department": context.department,
            "has_department_type": context.department.department_type_id is not None,
            "active_surgery_tab": "procedures",
        },
    )


@router.get("/my-surgery-education")
async def my_surgery_education_page(
    request: Request,
    context: AccessContext = Depends(get_access_context),
    journey: PatientJourneyProfile = Depends(get_active_journey),
    db: Session = Depends(get_db),
):
    groups = get_surgery_education_groups(
        db, journey,
        patient_access_profile_id=context.patient_profile.id,
        hospital_id=context.hospital_id,
        department_id=context.department_id,
        department_type_id=context.department.department_type_id,
    )

    return templates.TemplateResponse(
        request,
        "patient_surgery_education.html",
        {
            "request": request,
            "groups": groups,
            "active_surgery_tab": "education",
        },
    )


@router.get("/patient-auth/procedures/options", response_model=list[ProcedureOptionResponse])
async def get_procedure_options(
    context: AccessContext = Depends(get_access_context),
    journey: PatientJourneyProfile = Depends(get_active_journey),
    db: Session = Depends(get_db),
):
    department_type_id = context.department.department_type_id
    if not department_type_id:
        return []

    procedures = list_procedures(db, department_type_id, include_inactive=False)
    selected_ids = set(patient_procedure_service.get_effective_procedure_ids(db, journey))

    return [
        ProcedureOptionResponse(id=p.id, name=p.name, is_selected=p.id in selected_ids)
        for p in procedures
    ]


@router.put("/patient-auth/procedures/selected")
async def update_selected_procedures(
    payload: ProcedureSelectionUpdateRequest,
    context: AccessContext = Depends(get_access_context),
    journey: PatientJourneyProfile = Depends(get_active_journey),
    db: Session = Depends(get_db),
):
    department_type_id = context.department.department_type_id
    if not department_type_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "این بخش نوع مشخصی ندارد.")

    selected = patient_procedure_service.set_selected_procedures(
        db, context.patient_profile.id, department_type_id, payload.procedure_ids,
    )

    if selected and journey.has_surgery is not True:
        journey.has_surgery = True
        db.commit()

    return JSONResponse({
        "selected_procedure_ids": [str(p.id) for p in selected],
        "selected_procedure_names": [p.name for p in selected],
    })