"""
app/api/v1/patient_medications.py

بخش «آموزش دارویی» - مستقل از مراحل سفر بیمار؛ بیمار هر زمان که
بخواهد می‌تواند نام دارو را جستجو کند و آموزش مربوطه را ببیند.
"""

import uuid

from fastapi import APIRouter, Request, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.infrastructure.db.session import get_db
from app.api.deps import AccessContext, get_access_context
from app.services.content_admin import medication_service
from app.core.templates import templates

router = APIRouter(tags=["patient_medications"])


@router.get("/my-medications")
async def my_medications_page(
    request: Request,
    q: str | None = None,
    context: AccessContext = Depends(get_access_context),
    db: Session = Depends(get_db),
):
    department_type_id = context.department.department_type_id
    medications = medication_service.search_medications_for_patient(db, department_type_id, q)

    return templates.TemplateResponse(
        request,
        "patient_medications.html",
        {"request": request, "medications": medications, "q": q or ""},
    )


@router.get("/medications/{medication_id}")
async def medication_detail(
    request: Request,
    medication_id: uuid.UUID,
    context: AccessContext = Depends(get_access_context),
    db: Session = Depends(get_db),
):
    department_type_id = context.department.department_type_id
    medication = medication_service.get_active_medication_for_patient(db, medication_id, department_type_id)
    if not medication:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "دارو پیدا نشد.")

    return templates.TemplateResponse(
        request,
        "medication_detail.html",
        {"request": request, "medication": medication},
    )