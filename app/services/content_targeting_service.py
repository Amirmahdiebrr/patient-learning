"""
app/services/content_targeting_service.py

Resolves published lessons AND stage-level quiz questions for a
patient journey.

Lessons: structural match (journey_stage + department_type) with
hospital-level override resolution and optional ContentTargetingRule
filtering - see get_lessons_for_journey.

Stage quiz: a simpler match - QuizQuestion.journey_stage matches the
patient's current stage, AND (department_type_id is NULL [general] OR
matches the patient's department type). No hospital-override or
targeting-rule layer for quiz questions (not requested / not needed
yet) - keep it simple until a real need for per-hospital quiz
overrides shows up.
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
    QuizQuestion,
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


def get_stage_quiz_for_journey(
    db: Session,
    journey: PatientJourneyProfile,
    department_type_id: uuid.UUID | None,
) -> list[QuizQuestion]:
    return (
        db.query(QuizQuestion)
        .filter(
            QuizQuestion.journey_stage.has(code=journey.current_stage),
            or_(
                QuizQuestion.department_type_id.is_(None),
                QuizQuestion.department_type_id == department_type_id,
            ),
        )
        .order_by(QuizQuestion.display_order)
        .all()
    )