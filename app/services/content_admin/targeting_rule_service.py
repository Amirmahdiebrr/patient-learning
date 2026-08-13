"""
app/services/content_admin/targeting_rule_service.py
"""

import uuid

from sqlalchemy.orm import Session

from app.infrastructure.db.models import ContentTargetingRule, Lesson, Hospital, Department
from app.services.content_admin.errors import ContentNotFoundError


def create_targeting_rule(
    db: Session,
    lesson_id: uuid.UUID,
    hospital_id: uuid.UUID | None,
    department_id: uuid.UUID | None,
    disease_id: uuid.UUID | None,
    treatment_id: uuid.UUID | None,
    min_age: int | None,
    max_age: int | None,
    gender: str | None,
    priority: int,
) -> ContentTargetingRule:
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise ContentNotFoundError("درس پیدا نشد.")

    if hospital_id and not db.query(Hospital).filter(Hospital.id == hospital_id).first():
        raise ContentNotFoundError("بیمارستان پیدا نشد.")

    if department_id:
        dept_query = db.query(Department).filter(Department.id == department_id)
        if hospital_id:
            dept_query = dept_query.filter(Department.hospital_id == hospital_id)
        if not dept_query.first():
            raise ContentNotFoundError("بخش پیدا نشد یا به این بیمارستان تعلق ندارد.")

    rule = ContentTargetingRule(
        lesson_id=lesson_id, hospital_id=hospital_id, department_id=department_id,
        disease_id=disease_id, treatment_id=treatment_id,
        min_age=min_age, max_age=max_age, gender=gender, priority=priority,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def list_targeting_rules(db: Session, lesson_id: uuid.UUID) -> list[ContentTargetingRule]:
    return (
        db.query(ContentTargetingRule)
        .filter(ContentTargetingRule.lesson_id == lesson_id)
        .order_by(ContentTargetingRule.priority.desc())
        .all()
    )


def delete_targeting_rule(db: Session, rule_id: uuid.UUID) -> None:
    rule = db.query(ContentTargetingRule).filter(ContentTargetingRule.id == rule_id).first()
    if not rule:
        raise ContentNotFoundError("این قانون پیدا نشد.")
    db.delete(rule)
    db.commit()