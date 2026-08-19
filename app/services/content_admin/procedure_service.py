# app/services/content_admin/procedure_service.py
"""
app/services/content_admin/procedure_service.py

Procedure CRUD, always scoped to a StandardDepartmentType. A
procedure belongs to exactly one department - it is never
cross-assigned, so downstream section/quiz validation can trust
Procedure.department_type_id as the source of truth.
"""

import uuid

from sqlalchemy.orm import Session

from app.infrastructure.db.models import Procedure, StandardDepartmentType
from app.schemas.content_admin import slugify
from app.services.content_admin.errors import ContentNotFoundError


def create_procedure(db: Session, department_type_id: uuid.UUID, name: str, display_order: int) -> Procedure:
    dept_type = db.query(StandardDepartmentType).filter(StandardDepartmentType.id == department_type_id).first()
    if not dept_type:
        raise ContentNotFoundError("نوع بخش استاندارد پیدا نشد.")

    procedure = Procedure(
        department_type_id=department_type_id,
        name=name,
        slug=slugify(name),
        display_order=display_order,
    )
    db.add(procedure)
    db.commit()
    db.refresh(procedure)
    return procedure


def list_procedures(db: Session, department_type_id: uuid.UUID, include_inactive: bool = False) -> list[Procedure]:
    query = db.query(Procedure).filter(Procedure.department_type_id == department_type_id)
    if not include_inactive:
        query = query.filter(Procedure.is_active.is_(True))
    return query.order_by(Procedure.display_order, Procedure.name).all()


def get_procedure_or_raise(db: Session, procedure_id: uuid.UUID) -> Procedure:
    procedure = db.query(Procedure).filter(Procedure.id == procedure_id).first()
    if not procedure:
        raise ContentNotFoundError("عمل/پروسیجر پیدا نشد.")
    return procedure


def update_procedure(
    db: Session, procedure_id: uuid.UUID, name: str, is_active: bool, display_order: int,
) -> Procedure:
    procedure = get_procedure_or_raise(db, procedure_id)
    procedure.name = name
    procedure.slug = slugify(name)
    procedure.is_active = is_active
    procedure.display_order = display_order
    db.commit()
    db.refresh(procedure)
    return procedure


def set_procedure_active(db: Session, procedure_id: uuid.UUID, is_active: bool) -> Procedure:
    procedure = get_procedure_or_raise(db, procedure_id)
    procedure.is_active = is_active
    db.commit()
    db.refresh(procedure)
    return procedure


def validate_procedure_matches_department(
    db: Session, procedure_id: uuid.UUID | None, department_type_id: uuid.UUID | None,
) -> None:
    """
    Raises if procedure_id is given but doesn't belong to
    department_type_id (or department_type_id is missing entirely -
    a procedure is always department-specific, never "general").
    """
    if not procedure_id:
        return
    if not department_type_id:
        raise ContentNotFoundError("انتخاب عمل فقط برای یک نوع بخش مشخص ممکن است.")

    procedure = get_procedure_or_raise(db, procedure_id)
    if procedure.department_type_id != department_type_id:
        raise ContentNotFoundError("این عمل متعلق به این نوع بخش نیست.")