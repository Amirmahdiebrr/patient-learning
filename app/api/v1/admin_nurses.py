"""
app/api/v1/admin_nurses.py

Hospital-scoped admin review of nurse self-registration requests: a
nurse cannot log in (NurseUser.is_active=False) until an admin with
access to her hospital approves her here.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import AdminUser, NurseUser
from app.schemas.nurse import NurseAdminRowResponse, NurseAdminListResponse
from app.api.deps_admin import get_current_admin
from app.infrastructure.db.repositories.hospital_scoped_repository import ensure_hospital_access

router = APIRouter(prefix="/admin", tags=["admin_nurses"])


def _to_response(nurse: NurseUser) -> NurseAdminRowResponse:
    return NurseAdminRowResponse(
        id=nurse.id,
        full_name=nurse.full_name,
        email=nurse.email,
        national_id=nurse.national_id,
        nursing_license_number=nurse.nursing_license_number,
        hospital_name=nurse.hospital.name,
        department_name=nurse.department.name if nurse.department else None,
        is_active=nurse.is_active,
        created_at=nurse.created_at,
        approved_at=nurse.approved_at,
    )


@router.get("/nurses", response_model=NurseAdminListResponse)
async def list_nurses(
    hospital_id: uuid.UUID,
    only_pending: bool = False,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    ensure_hospital_access(admin, db, hospital_id)

    query = db.query(NurseUser).filter(NurseUser.hospital_id == hospital_id)
    if only_pending:
        query = query.filter(NurseUser.is_active.is_(False))

    nurses = query.order_by(NurseUser.created_at.desc()).all()

    return NurseAdminListResponse(total=len(nurses), rows=[_to_response(n) for n in nurses])


@router.post("/nurses/{nurse_id}/approve", response_model=NurseAdminRowResponse)
async def approve_nurse(
    nurse_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    nurse = db.query(NurseUser).filter(NurseUser.id == nurse_id).first()
    if not nurse:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "درخواست پرستار پیدا نشد.")

    ensure_hospital_access(admin, db, nurse.hospital_id)

    nurse.is_active = True
    nurse.approved_at = datetime.utcnow()
    db.commit()
    db.refresh(nurse)

    return _to_response(nurse)


@router.post("/nurses/{nurse_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
async def reject_nurse(
    nurse_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    nurse = db.query(NurseUser).filter(NurseUser.id == nurse_id).first()
    if not nurse:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "درخواست پرستار پیدا نشد.")

    ensure_hospital_access(admin, db, nurse.hospital_id)

    db.delete(nurse)
    db.commit()


@router.post("/nurses/{nurse_id}/deactivate", response_model=NurseAdminRowResponse)
async def deactivate_nurse(
    nurse_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    nurse = db.query(NurseUser).filter(NurseUser.id == nurse_id).first()
    if not nurse:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "پرستار پیدا نشد.")

    ensure_hospital_access(admin, db, nurse.hospital_id)

    nurse.is_active = False
    nurse.approved_at = None
    db.commit()
    db.refresh(nurse)

    return _to_response(nurse)