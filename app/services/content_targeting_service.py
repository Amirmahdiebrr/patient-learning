"""
app/services/content_targeting_service.py

Resolves which published lessons should be shown to a given patient
journey, combining two matching layers:

1. Structural match: EducationSection.journey_stage == patient's
   current_stage, AND (section.treatment_id is NULL [general] OR
   section.treatment_id == patient's treatment_id).
2. Fine-grained override: ContentTargetingRule rows on the lesson
   (hospital/department/disease/treatment/age/gender). A lesson with
   at least one rule must match at least one of its rules; a lesson
   with zero rules is shown to everyone matching the structural layer.
"""

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.infrastructure.db.models import (
    Lesson,
    EducationSection,
    ContentTargetingRule,
    PatientJourneyProfile,
)


def _rule_matches(rule: ContentTargetingRule, journey: PatientJourneyProfile) -> bool:
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


def get_lessons_for_journey(db: Session, journey: PatientJourneyProfile) -> list[Lesson]:
    """
    Returns published lessons relevant to this patient's current
    stage and condition, ordered by section/lesson display_order.
    """

    sections = (
        db.query(EducationSection)
        .filter(
            EducationSection.journey_stage.has(code=journey.current_stage),
            EducationSection.is_active.is_(True),
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

            if any(_rule_matches(rule, journey) for rule in lesson.targeting_rules):
                matched_lessons.append(lesson)

    return matched_lessons