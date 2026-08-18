"""
app/services/content_admin/section_service.py

EducationSection CRUD. journey_stage/department_type/treatment
existence checks live here so the route layer stays a thin
validation+call wrapper. section_snapshot() is exported for the route
to build AdminContentAction before/after payloads.

delete_section() now cascades: deleting a section also deletes every
lesson inside it (and, via ORM cascade on Lesson's relationships,
their media_assets/quiz_questions/quiz_options/targeting_rules), after
first clearing the non-cascaded FKs (favorite_records, progress_records,
quiz_attempts, feedback_records) exactly like lesson_service.delete_lesson
does for a single lesson.
"""

import uuid

from sqlalchemy.orm import Session

from app.infrastructure.db.models import (
    EducationSection, JourneyStage, StandardDepartmentType, Treatment,
    Lesson, QuizQuestion, QuizAttempt, FavoriteRecord, ProgressRecord, FeedbackRecord,
)
from app.services.content_admin.errors import ContentNotFoundError


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


def _delete_lesson_dependencies(db: Session, lesson: Lesson) -> None:
    question_ids = [
        row[0] for row in
        db.query(QuizQuestion.id).filter(QuizQuestion.lesson_id == lesson.id).all()
    ]
    if question_ids:
        db.query(QuizAttempt).filter(QuizAttempt.question_id.in_(question_ids)).delete(synchronize_session=False)

    db.query(FavoriteRecord).filter(FavoriteRecord.lesson_id == lesson.id).delete(synchronize_session=False)
    db.query(ProgressRecord).filter(ProgressRecord.lesson_id == lesson.id).delete(synchronize_session=False)
    db.query(FeedbackRecord).filter(FeedbackRecord.lesson_id == lesson.id).update(
        {FeedbackRecord.lesson_id: None}, synchronize_session=False
    )


def delete_section(db: Session, section_id: uuid.UUID) -> tuple[uuid.UUID, dict]:
    section = get_section_or_raise(db, section_id)

    before = section_snapshot(section)
    section_id_copy = section.id

    for lesson in list(section.lessons):
        _delete_lesson_dependencies(db, lesson)
        db.delete(lesson)

    db.delete(section)
    db.commit()

    return section_id_copy, before