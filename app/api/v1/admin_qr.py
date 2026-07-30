"""
app/api/v1/admin_qr.py

Admin CRUD for QRAccessPoint: create (generates the token + returns
the full entry URL to encode into a printed QR image), list, revoke.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import QRAccessPoint, QRAccessPointStatus, AdminUser, Department
from app.schemas.admin import QRAccessPointCreateRequest, QRAccessPointResponse
from app.api.deps_admin import get_current_admin, require_hospital_scope
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
    if not require_hospital_scope(admin, db, payload.hospital_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "دسترسی به این بیمارستان ندارید.")

    department = (
        db.query(Department)
        .filter(Department.id == payload.department_id, Department.hospital_id == payload.hospital_id)
        .first()
    )
    if not department:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "بخش پیدا نشد یا به این بیمارستان تعلق ندارد.")

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
    if not require_hospital_scope(admin, db, hospital_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "دسترسی به این بیمارستان ندارید.")

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

    if not require_hospital_scope(admin, db, access_point.hospital_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "دسترسی به این بیمارستان ندارید.")

    from datetime import datetime
    access_point.status = QRAccessPointStatus.REVOKED
    access_point.revoked_at = datetime.utcnow()
    db.commit()
    db.refresh(access_point)

    return _to_response(access_point)