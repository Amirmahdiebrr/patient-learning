"""
app/services/content_targeting_service.py

Resolves which published lessons should be shown to a given patient
journey, combining two matching layers:

1. Structural match (the main scoping mechanism):
   EducationSection.journey_stage == patient's current_stage, AND
   (section.department_type_id is NULL [general - shown to every
   department] OR section.department_type_id == the patient's
   department's department_type_id), AND (section.treatment_id is
   NULL [general] OR section.treatment_id == patient's treatment_id).
   This is what makes content a shared library: build it once per
   department type, and every hospital with a Department of that type
   gets it automatically - no per-hospital linking required.

2. Fine-grained OPTIONAL override: ContentTargetingRule rows on the
   lesson (age/gender/disease/treatment, or a specific hospital/
   department for a rare one-off exception). A lesson with at least
   one rule must match at least one of its rules; a lesson with zero
   rules is shown to everyone matching the structural layer.
"""

import uuid

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.infrastructure.db.models import (
    Lesson,
    EducationSection,
    ContentTargetingRule,
    PatientJourneyProfile,
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


def get_lessons_for_journey(
    db: Session,
    journey: PatientJourneyProfile,
    hospital_id: uuid.UUID,
    department_id: uuid.UUID,
    department_type_id: uuid.UUID | None,
) -> list[Lesson]:
    """
    Returns published lessons relevant to this patient's current
    stage, department type and condition, ordered by section/lesson
    display_order.
    """

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
            if not lesson.is_published:
                continue

            if not lesson.targeting_rules:
                matched_lessons.append(lesson)
                continue

            if any(
                _rule_matches(rule, journey, hospital_id, department_id)
                for rule in lesson.targeting_rules
            ):
                matched_lessons.append(lesson)

    return matched_lessons