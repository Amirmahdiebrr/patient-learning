"""
app/services/content_admin/section_service.py

EducationSection CRUD. journey_stage/department_type/treatment
existence checks live here so the route layer stays a thin
validation+call wrapper. section_snapshot() is exported for the route
to build AdminContentAction before/after payloads.
"""

import uuid

from sqlalchemy.orm import Session

from app.infrastructure.db.models import EducationSection, JourneyStage, StandardDepartmentType, Treatment
from app.services.content_admin.errors import ContentNotFoundError, ContentConflictError


def section_snapshot(section: EducationSection) -> dict:
    return {
        "title": section.title,
        "journey_stage_id": str(section.journey_stage_id),
        "department_type_id": str(section.department_type_id) if section.department_type_id else None,
        "treatment_id": str(section.treatment_id) if section.treatment_id else None,
        "is_active": section.is_active,
    }


def _validate_refs(
    db: Session,
    journey_stage_id: uuid.UUID,
    department_type_id: uuid.UUID | None,
    treatment_id: uuid.UUID | None,
) -> None:
    if not db.query(JourneyStage).filter(JourneyStage.id == journey_stage_id).first():
        raise ContentNotFoundError("مرحله‌ی سفر بیمار پیدا نشد.")

    if department_type_id and not db.query(StandardDepartmentType).filter(
        StandardDepartmentType.id == department_type_id
    ).first():
        raise ContentNotFoundError("نوع بخش استاندارد پیدا نشد.")

    if treatment_id and not db.query(Treatment).filter(Treatment.id == treatment_id).first():
        raise ContentNotFoundError("درمان/عمل پیدا نشد.")


def create_section(
    db: Session,
    journey_stage_id: uuid.UUID,
    department_type_id: uuid.UUID | None,
    treatment_id: uuid.UUID | None,
    title: str,
    display_order: int,
) -> EducationSection:
    _validate_refs(db, journey_stage_id, department_type_id, treatment_id)

    section = EducationSection(
        journey_stage_id=journey_stage_id,
        department_type_id=department_type_id,
        treatment_id=treatment_id,
        title=title,
        display_order=display_order,
    )
    db.add(section)
    db.commit()
    db.refresh(section)
    return section


def list_sections(
    db: Session,
    journey_stage_id: uuid.UUID | None,
    department_type_id: uuid.UUID | None,
    department_type_is_general: bool,
    include_inactive: bool,
) -> list[EducationSection]:
    query = db.query(EducationSection)
    if not include_inactive:
        query = query.filter(EducationSection.is_active.is_(True))
    if journey_stage_id:
        query = query.filter(EducationSection.journey_stage_id == journey_stage_id)
    if department_type_is_general:
        query = query.filter(EducationSection.department_type_id.is_(None))
    elif department_type_id:
        query = query.filter(EducationSection.department_type_id == department_type_id)

    return query.order_by(EducationSection.display_order).all()


def get_section_or_raise(db: Session, section_id: uuid.UUID) -> EducationSection:
    section = db.query(EducationSection).filter(EducationSection.id == section_id).first()
    if not section:
        raise ContentNotFoundError("بخش آموزشی پیدا نشد.")
    return section


def update_section(
    db: Session,
    section_id: uuid.UUID,
    journey_stage_id: uuid.UUID,
    department_type_id: uuid.UUID | None,
    treatment_id: uuid.UUID | None,
    title: str,
) -> tuple[EducationSection, dict]:
    section = get_section_or_raise(db, section_id)
    _validate_refs(db, journey_stage_id, department_type_id, treatment_id)

    before = section_snapshot(section)

    section.journey_stage_id = journey_stage_id
    section.department_type_id = department_type_id
    section.treatment_id = treatment_id
    section.title = title
    db.commit()
    db.refresh(section)

    return section, before


def set_section_active(db: Session, section_id: uuid.UUID, is_active: bool) -> tuple[EducationSection, dict]:
    section = get_section_or_raise(db, section_id)
    before = section_snapshot(section)
    section.is_active = is_active
    db.commit()
    db.refresh(section)
    return section, before


def delete_section(db: Session, section_id: uuid.UUID) -> tuple[uuid.UUID, dict]:
    section = get_section_or_raise(db, section_id)

    if section.lessons:
        raise ContentConflictError(
            "این بخش درس دارد؛ ابتدا درس‌های داخل آن را حذف کنید یا این بخش را غیرفعال کنید."
        )

    before = section_snapshot(section)
    section_id_copy = section.id

    db.delete(section)
    db.commit()

    return section_id_copy, before