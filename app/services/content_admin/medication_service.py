"""
app/services/content_admin/medication_service.py

CRUD داروها برای پنل ادمین + توابع جستجو/دریافت برای سمت بیمار.
department_type_id نال یعنی دارو «عمومی» است.
"""

import uuid

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.sanitize import sanitize_html
from app.infrastructure.db.models import Medication, StandardDepartmentType
from app.schemas.content_admin import slugify
from app.services.content_admin.errors import ContentNotFoundError


def create_medication(
    db: Session,
    department_type_id: uuid.UUID | None,
    name: str,
    body_richtext: str | None,
    image_url: str | None,
    display_order: int,
) -> Medication:
    if department_type_id and not db.query(StandardDepartmentType).filter(
        StandardDepartmentType.id == department_type_id
    ).first():
        raise ContentNotFoundError("نوع بخش استاندارد پیدا نشد.")

    medication = Medication(
        department_type_id=department_type_id,
        name=name,
        slug=slugify(name),
        body_richtext=sanitize_html(body_richtext),
        image_url=image_url,
        display_order=display_order,
    )
    db.add(medication)
    db.commit()
    db.refresh(medication)
    return medication


def list_medications(
    db: Session,
    department_type_id: uuid.UUID | None,
    department_type_is_general: bool,
    include_inactive: bool = False,
) -> list[Medication]:
    query = db.query(Medication)
    if not include_inactive:
        query = query.filter(Medication.is_active.is_(True))
    if department_type_is_general:
        query = query.filter(Medication.department_type_id.is_(None))
    elif department_type_id:
        query = query.filter(Medication.department_type_id == department_type_id)
    return query.order_by(Medication.display_order, Medication.name).all()


def get_medication_or_raise(db: Session, medication_id: uuid.UUID) -> Medication:
    medication = db.query(Medication).filter(Medication.id == medication_id).first()
    if not medication:
        raise ContentNotFoundError("دارو پیدا نشد.")
    return medication


def update_medication(
    db: Session,
    medication_id: uuid.UUID,
    name: str,
    body_richtext: str | None,
    image_url: str | None,
    is_active: bool,
    display_order: int,
) -> Medication:
    medication = get_medication_or_raise(db, medication_id)
    medication.name = name
    medication.slug = slugify(name)
    medication.body_richtext = sanitize_html(body_richtext)
    medication.image_url = image_url
    medication.is_active = is_active
    medication.display_order = display_order
    db.commit()
    db.refresh(medication)
    return medication


def set_medication_active(db: Session, medication_id: uuid.UUID, is_active: bool) -> Medication:
    medication = get_medication_or_raise(db, medication_id)
    medication.is_active = is_active
    db.commit()
    db.refresh(medication)
    return medication


def delete_medication(db: Session, medication_id: uuid.UUID) -> None:
    medication = get_medication_or_raise(db, medication_id)
    db.delete(medication)
    db.commit()


def search_medications_for_patient(
    db: Session, department_type_id: uuid.UUID | None, q: str | None,
) -> list[Medication]:
    query = db.query(Medication).filter(Medication.is_active.is_(True))
    if department_type_id:
        query = query.filter(
            or_(Medication.department_type_id.is_(None), Medication.department_type_id == department_type_id)
        )
    else:
        query = query.filter(Medication.department_type_id.is_(None))

    if q and q.strip():
        query = query.filter(Medication.name.ilike(f"%{q.strip()}%"))

    return query.order_by(Medication.display_order, Medication.name).all()


def get_active_medication_for_patient(
    db: Session, medication_id: uuid.UUID, department_type_id: uuid.UUID | None,
) -> Medication | None:
    medication = db.query(Medication).filter(
        Medication.id == medication_id, Medication.is_active.is_(True)
    ).first()
    if not medication:
        return None
    if medication.department_type_id is not None and medication.department_type_id != department_type_id:
        return None
    return medication