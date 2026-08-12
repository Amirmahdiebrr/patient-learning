"""
app/api/v1/admin_qr.py

Admin CRUD for QRAccessPoint: create (generates the token + returns
the full entry URL to encode into a printed QR image), list, revoke.

Uses ensure_department_access (not just ensure_hospital_access) for
create/revoke, since a QR access point belongs to one specific
department - a department_admin scoped to Orthopedics must not be
able to create or revoke a QR for Cardiology just because both sit
under the same hospital.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import QRAccessPoint, QRAccessPointStatus, AdminUser, Department
from app.schemas.admin import QRAccessPointCreateRequest, QRAccessPointResponse
from app.api.deps_admin import get_current_admin
from app.infrastructure.db.repositories.hospital_scoped_repository import (
    ensure_hospital_access, ensure_department_access,
)
from app.services.access_gate_service import generate_qr_token

router = APIRouter(prefix="/admin/qr-access-points", tags=["admin_qr"])


def _to_response(access_point: QRAccessPoint) -> QRAccessPointResponse:
    return QRAccessPointResponse(
        id=access_point.id,
        hospital_id=access_point.hospital_id,
        department_id=access_point.department_id,
        label=access_point.label,
        status=access_point.status.value,
        entry_url=f"{settings.APP_BASE_URL}/entry?token={access_point.access_token}",
        created_at=access_point.created_at,
    )


@router.post("", response_model=QRAccessPointResponse)
async def create_qr_access_point(
    payload: QRAccessPointCreateRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    department = (
        db.query(Department)
        .filter(Department.id == payload.department_id, Department.hospital_id == payload.hospital_id)
        .first()
    )
    if not department:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "بخش پیدا نشد یا به این بیمارستان تعلق ندارد.")

    ensure_department_access(admin, db, payload.hospital_id, payload.department_id)

    access_point = QRAccessPoint(
        hospital_id=payload.hospital_id,
        department_id=payload.department_id,
        access_token=generate_qr_token(),
        label=payload.label,
        status=QRAccessPointStatus.ACTIVE,
        created_by_admin_id=admin.id,
    )
    db.add(access_point)
    db.commit()
    db.refresh(access_point)

    return _to_response(access_point)


@router.get("", response_model=list[QRAccessPointResponse])
async def list_qr_access_points(
    hospital_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    ensure_hospital_access(admin, db, hospital_id)

    access_points = (
        db.query(QRAccessPoint)
        .filter(QRAccessPoint.hospital_id == hospital_id)
        .order_by(QRAccessPoint.created_at.desc())
        .all()
    )
    return [_to_response(a) for a in access_points]


@router.post("/{access_point_id}/revoke", response_model=QRAccessPointResponse)
async def revoke_qr_access_point(
    access_point_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    access_point = db.query(QRAccessPoint).filter(QRAccessPoint.id == access_point_id).first()
    if not access_point:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "این QR پیدا نشد.")

    ensure_department_access(admin, db, access_point.hospital_id, access_point.department_id)

    access_point.status = QRAccessPointStatus.REVOKED
    access_point.revoked_at = datetime.utcnow()
    db.commit()
    db.refresh(access_point)

    return _to_response(access_point)