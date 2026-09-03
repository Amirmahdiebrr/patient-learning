"""
app/api/v1/admin_medications.py
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import AdminUser, RoleCode
from app.schemas.medication import MedicationCreateRequest, MedicationUpdateRequest, MedicationResponse
from app.api.deps_admin import ScopeCheck
from app.services.content_admin import medication_service
from app.services.content_admin.errors import ContentNotFoundError

router = APIRouter(prefix="/admin", tags=["admin_medications"])

require_content_editor = ScopeCheck(allowed_roles=(RoleCode.SUPER_ADMIN, RoleCode.CONTENT_MANAGER))


def _raise_for(exc: Exception):
    if isinstance(exc, ContentNotFoundError):
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    raise exc


def _parse_department_type_id(raw: str | None) -> tuple[uuid.UUID | None, bool]:
    if raw == "general":
        return None, True
    if raw:
        try:
            return uuid.UUID(raw), False
        except ValueError:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "شناسه‌ی نوع بخش نامعتبر است.")
    return None, False


def _to_response(m) -> MedicationResponse:
    return MedicationResponse(
        id=m.id,
        department_type_id=m.department_type_id,
        department_type_name=m.department_type.name if m.department_type else None,
        name=m.name,
        slug=m.slug,
        body_richtext=m.body_richtext,
        image_url=m.image_url,
        is_active=m.is_active,
        display_order=m.display_order,
    )


@router.post("/medications", response_model=MedicationResponse)
async def create_medication(
    payload: MedicationCreateRequest,
    admin: AdminUser = Depends(require_content_editor()),
    db: Session = Depends(get_db),
):
    try:
        medication = medication_service.create_medication(
            db, payload.department_type_id, payload.name, payload.body_richtext,
            payload.image_url, payload.display_order,
        )
    except ContentNotFoundError as exc:
        _raise_for(exc)
    return _to_response(medication)


@router.get("/medications", response_model=list[MedicationResponse])
async def list_medications(
    department_type_id: str | None = None,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
):
    parsed_id, is_general = _parse_department_type_id(department_type_id)
    medications = medication_service.list_medications(db, parsed_id, is_general, include_inactive)
    return [_to_response(m) for m in medications]


@router.patch("/medications/{medication_id}", response_model=MedicationResponse)
async def update_medication(
    medication_id: uuid.UUID,
    payload: MedicationUpdateRequest,
    admin: AdminUser = Depends(require_content_editor()),
    db: Session = Depends(get_db),
):
    try:
        medication = medication_service.update_medication(
            db, medication_id, payload.name, payload.body_richtext,
            payload.image_url, payload.is_active, payload.display_order,
        )
    except ContentNotFoundError as exc:
        _raise_for(exc)
    return _to_response(medication)


@router.post("/medications/{medication_id}/deactivate", response_model=MedicationResponse)
async def deactivate_medication(
    medication_id: uuid.UUID,
    admin: AdminUser = Depends(require_content_editor()),
    db: Session = Depends(get_db),
):
    try:
        medication = medication_service.set_medication_active(db, medication_id, False)
    except ContentNotFoundError as exc:
        _raise_for(exc)
    return _to_response(medication)


@router.post("/medications/{medication_id}/reactivate", response_model=MedicationResponse)
async def reactivate_medication(
    medication_id: uuid.UUID,
    admin: AdminUser = Depends(require_content_editor()),
    db: Session = Depends(get_db),
):
    try:
        medication = medication_service.set_medication_active(db, medication_id, True)
    except ContentNotFoundError as exc:
        _raise_for(exc)
    return _to_response(medication)


@router.delete("/medications/{medication_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_medication(
    medication_id: uuid.UUID,
    admin: AdminUser = Depends(require_content_editor()),
    db: Session = Depends(get_db),
):
    try:
        medication_service.delete_medication(db, medication_id)
    except ContentNotFoundError as exc:
        _raise_for(exc)