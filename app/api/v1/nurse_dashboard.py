"""
app/api/v1/nurse_dashboard.py

Nurse-facing pages + JSON API. hospital_id/department_id always come
from the logged-in nurse's own profile (never from client input), so
a nurse can only ever see her own hospital/department - this also
fixes the earlier "hospital_id required" error, which happened
because the monitoring endpoint expected the caller to supply scope.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_nurse_access_token
from app.core.templates import templates
from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import NurseUser
from app.api.deps_nurse import get_current_nurse
from app.schemas.nurse import NurseMeResponse
from app.schemas.patient_monitoring import PatientMonitoringResponse, PatientMonitoringRowResponse
from app.services.patient_monitoring_service import get_patient_monitoring

router = APIRouter(tags=["nurse_dashboard"])


# ---------------- HTML pages ----------------

@router.get("/nurse/login")
async def nurse_login_page(request: Request):
    return templates.TemplateResponse(request, "nurse_login.html", {"request": request})


@router.get("/nurse/register")
async def nurse_register_page(request: Request):
    return templates.TemplateResponse(request, "nurse_register.html", {"request": request})


@router.get("/nurse/dashboard")
async def nurse_dashboard_page(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get(settings.NURSE_TOKEN_COOKIE_NAME)
    nurse_id = decode_nurse_access_token(token) if token else None
    if not nurse_id:
        return RedirectResponse(url="/nurse/login", status_code=303)

    nurse = db.query(NurseUser).filter(NurseUser.id == nurse_id, NurseUser.is_active.is_(True)).first()
    if not nurse:
        return RedirectResponse(url="/nurse/login", status_code=303)

    return templates.TemplateResponse(
        request,
        "nurse_dashboard.html",
        {
            "request": request,
            "csrf_token": request.cookies.get(settings.NURSE_CSRF_COOKIE_NAME),
        },
    )


# ---------------- JSON API ----------------

@router.get("/nurse/api/me", response_model=NurseMeResponse)
async def nurse_me(
    nurse: NurseUser = Depends(get_current_nurse),
):
    return NurseMeResponse(
        full_name=nurse.full_name,
        email=nurse.email,
        hospital_name=nurse.hospital.name,
        department_name=nurse.department.name if nurse.department else None,
    )


@router.get("/nurse/api/patient-monitoring", response_model=PatientMonitoringResponse)
async def nurse_patient_monitoring(
    search: str | None = None,
    only_needs_attention: bool = False,
    limit: int = 100,
    offset: int = 0,
    nurse: NurseUser = Depends(get_current_nurse),
    db: Session = Depends(get_db),
):
    total, rows = get_patient_monitoring(
        db,
        hospital_id=nurse.hospital_id,
        department_id=nurse.department_id,
        search=search,
        only_needs_attention=only_needs_attention,
        limit=min(limit, 200),
        offset=offset,
    )

    return PatientMonitoringResponse(
        total=total,
        rows=[PatientMonitoringRowResponse(**row) for row in rows],
    )