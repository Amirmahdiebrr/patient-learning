"""
app/services/content_admin/lesson_service.py

Lesson CRUD, including hospital-level override lessons. HTML
sanitization of body_richtext happens here (not in the route) since
"never persist raw HTML" is a property of how a lesson is stored, not
of the HTTP layer.
"""

import uuid

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.core.sanitize import sanitize_html
from app.infrastructure.db.models import Lesson, EducationSection, Hospital, LessonOverrideLevel
from app.services.content_admin.errors import ContentNotFoundError, ContentConflictError, ContentValidationError


def lesson_snapshot(lesson: Lesson) -> dict:
    return {"title": lesson.title, "body_richtext": lesson.body_richtext, "is_published": lesson.is_published}


def create_lesson(
    db: Session, section_id: uuid.UUID, title: str, body_richtext: str | None,
    display_order: int, is_published: bool,
) -> Lesson:
    section = db.query(EducationSection).filter(EducationSection.id == section_id).first()
    if not section:
        raise ContentNotFoundError("بخش آموزشی پیدا نشد.")

    lesson = Lesson(
        section_id=section_id,
        title=title,
        body_richtext=sanitize_html(body_richtext),
        display_order=display_order,
        is_published=is_published,
        override_level=LessonOverrideLevel.GLOBAL,
    )
    db.add(lesson)
    db.commit()
    db.refresh(lesson)
    return lesson


def list_lessons_for_section(db: Session, section_id: uuid.UUID) -> list[Lesson]:
    return (
        db.query(Lesson)
        .filter(Lesson.section_id == section_id, Lesson.override_level == LessonOverrideLevel.GLOBAL)
        .order_by(Lesson.display_order)
        .all()
    )


def search_lessons(db: Session, q: str, limit: int) -> list[Lesson]:
    if not q or len(q.strip()) < 2:
        raise ContentValidationError("حداقل ۲ حرف برای جستجو وارد کنید.")

    term = f"%{q.strip()}%"
    return (
        db.query(Lesson)
        .join(EducationSection, Lesson.section_id == EducationSection.id)
        .options(
            joinedload(Lesson.section).joinedload(EducationSection.journey_stage),
            joinedload(Lesson.section).joinedload(EducationSection.department_type),
        )
        .filter(or_(Lesson.title.ilike(term), Lesson.body_richtext.ilike(term)))
        .order_by(Lesson.updated_at.desc())
        .limit(min(limit, 100))
        .all()
    )


def get_lesson_or_raise(db: Session, lesson_id: uuid.UUID) -> Lesson:
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise ContentNotFoundError("درس پیدا نشد.")
    return lesson


def update_lesson(db: Session, lesson_id: uuid.UUID, title: str, body_richtext: str | None) -> tuple[Lesson, dict]:
    lesson = get_lesson_or_raise(db, lesson_id)
    before = lesson_snapshot(lesson)

    lesson.title = title
    lesson.body_richtext = sanitize_html(body_richtext)
    db.commit()
    db.refresh(lesson)

    return lesson, before


def delete_lesson(db: Session, lesson_id: uuid.UUID) -> tuple[uuid.UUID, dict]:
    lesson = get_lesson_or_raise(db, lesson_id)
    before = lesson_snapshot(lesson)
    lesson_id_copy = lesson.id

    db.delete(lesson)
    db.commit()

    return lesson_id_copy, before


def set_lesson_published(db: Session, lesson_id: uuid.UUID, is_published: bool) -> tuple[Lesson, dict]:
    lesson = get_lesson_or_raise(db, lesson_id)
    before = lesson_snapshot(lesson)
    lesson.is_published = is_published
    db.commit()
    db.refresh(lesson)
    return lesson, before


def create_hospital_override(
    db: Session, lesson_id: uuid.UUID, hospital_id: uuid.UUID,
    title: str, body_richtext: str | None, is_published: bool,
) -> Lesson:
    base_lesson = get_lesson_or_raise(db, lesson_id)

    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise ContentNotFoundError("بیمارستان پیدا نشد.")

    existing = (
        db.query(Lesson)
        .filter(Lesson.parent_lesson_id == lesson_id, Lesson.hospital_id == hospital_id)
        .first()
    )
    if existing:
        raise ContentConflictError("این بیمارستان قبلاً یک نسخه‌ی اختصاصی برای این درس دارد.")

    override_lesson = Lesson(
        section_id=base_lesson.section_id,
        title=title,
        body_richtext=sanitize_html(body_richtext),
        display_order=base_lesson.display_order,
        is_published=is_published,
        override_level=LessonOverrideLevel.HOSPITAL,
        parent_lesson_id=lesson_id,
        hospital_id=hospital_id,
    )
    db.add(override_lesson)
    db.commit()
    db.refresh(override_lesson)
    return override_lesson


def list_hospital_overrides(db: Session, lesson_id: uuid.UUID) -> list[Lesson]:
    return db.query(Lesson).filter(Lesson.parent_lesson_id == lesson_id).order_by(Lesson.created_at.desc()).all()