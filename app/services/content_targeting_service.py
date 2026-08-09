"""
app/services/content_targeting_service.py

Resolves published lessons for a patient journey through:
1. Structural match (journey_stage + department_type, general or
   treatment-specific).
2. Hospital-level override resolution FIRST: if a HOSPITAL-scoped
   override Lesson exists for the base lesson and current hospital,
   it fully replaces the base lesson - independent of whether the
   base lesson itself is published. This lets a hospital publish its
   own override even while the shared global lesson stays in draft.
3. Optional ContentTargetingRule filtering (age/gender/disease/
   treatment), evaluated on whichever lesson (base or override) is
   ultimately shown.
"""

import uuid

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.infrastructure.db.models import (
    Lesson,
    EducationSection,
    ContentTargetingRule,
    PatientJourneyProfile,
    LessonOverrideLevel,
)


def _rule_matches(
    rule: ContentTargetingRule,
    journey: PatientJourneyProfile,
    hospital_id: uuid.UUID,
    department_id: uuid.UUID,
) -> bool:
    if rule.hospital_id and rule.hospital_id != hospital_id:
        return False
    if rule.department_id and rule.department_id != department_id:
        return False
    if rule.disease_id and rule.disease_id != journey.disease_id:
        return False
    if rule.treatment_id and rule.treatment_id != journey.treatment_id:
        return False
    if rule.min_age is not None and (journey.age is None or journey.age < rule.min_age):
        return False
    if rule.max_age is not None and (journey.age is None or journey.age > rule.max_age):
        return False
    if rule.gender and journey.gender and rule.gender != journey.gender:
        return False
    return True


def _resolve_effective_lesson(db: Session, base_lesson: Lesson, hospital_id: uuid.UUID) -> Lesson | None:
    """
    Returns the lesson that should actually be shown for this
    hospital: the hospital's published override if one exists,
    otherwise the base lesson IF it is published, otherwise None
    (nothing to show).
    """
    override = (
        db.query(Lesson)
        .filter(
            Lesson.parent_lesson_id == base_lesson.id,
            Lesson.hospital_id == hospital_id,
            Lesson.is_published.is_(True),
        )
        .first()
    )
    if override:
        return override

    return base_lesson if base_lesson.is_published else None


def get_lessons_for_journey(
    db: Session,
    journey: PatientJourneyProfile,
    hospital_id: uuid.UUID,
    department_id: uuid.UUID,
    department_type_id: uuid.UUID | None,
) -> list[Lesson]:

    sections = (
        db.query(EducationSection)
        .filter(
            EducationSection.journey_stage.has(code=journey.current_stage),
            EducationSection.is_active.is_(True),
            or_(
                EducationSection.department_type_id.is_(None),
                EducationSection.department_type_id == department_type_id,
            ),
            or_(
                EducationSection.treatment_id.is_(None),
                EducationSection.treatment_id == journey.treatment_id,
            ),
        )
        .order_by(EducationSection.display_order)
        .all()
    )

    matched_lessons: list[Lesson] = []

    for section in sections:
        for lesson in section.lessons:
            if lesson.override_level == LessonOverrideLevel.HOSPITAL:
                continue  # only surfaced via _resolve_effective_lesson below

            effective_lesson = _resolve_effective_lesson(db, lesson, hospital_id)
            if effective_lesson is None:
                continue

            if not lesson.targeting_rules:
                matched_lessons.append(effective_lesson)
                continue

            if any(
                _rule_matches(rule, journey, hospital_id, department_id)
                for rule in lesson.targeting_rules
            ):
                matched_lessons.append(effective_lesson)

    return matched_lessons