# app/services/content_admin/quiz_service.py
"""
app/services/content_admin/quiz_service.py

QuizQuestion CRUD - a question targets EITHER a single Lesson OR an
entire JourneyStage (optionally scoped to one department type and,
within that, one procedure); the exclusivity rule itself is enforced
at the schema layer (QuizQuestionCreateRequest's model_validator), so
this service only checks that whichever id(s) were actually given
point at real, consistent rows.
"""

import uuid

from sqlalchemy.orm import Session

from app.infrastructure.db.models import QuizQuestion, QuizOption, Lesson, JourneyStage, StandardDepartmentType
from app.schemas.content_admin import QuizOptionCreateRequest
from app.services.content_admin.errors import ContentNotFoundError
from app.services.content_admin.procedure_service import validate_procedure_matches_department


def create_quiz_question(
    db: Session,
    lesson_id: uuid.UUID | None,
    journey_stage_id: uuid.UUID | None,
    department_type_id: uuid.UUID | None,
    question_text: str,
    question_image_url: str | None,
    display_order: int,
    options: list[QuizOptionCreateRequest],
    procedure_id: uuid.UUID | None = None,
) -> QuizQuestion:
    if lesson_id and not db.query(Lesson).filter(Lesson.id == lesson_id).first():
        raise ContentNotFoundError("درس پیدا نشد.")

    if journey_stage_id and not db.query(JourneyStage).filter(JourneyStage.id == journey_stage_id).first():
        raise ContentNotFoundError("مرحله‌ی سفر بیمار پیدا نشد.")

    if department_type_id and not db.query(StandardDepartmentType).filter(
        StandardDepartmentType.id == department_type_id
    ).first():
        raise ContentNotFoundError("نوع بخش استاندارد پیدا نشد.")

    validate_procedure_matches_department(db, procedure_id, department_type_id)

    question = QuizQuestion(
        lesson_id=lesson_id,
        journey_stage_id=journey_stage_id,
        department_type_id=department_type_id,
        procedure_id=procedure_id,
        question_text=question_text,
        question_image_url=question_image_url,
        display_order=display_order,
    )
    db.add(question)
    db.flush()

    for i, opt in enumerate(options):
        db.add(QuizOption(
            question_id=question.id,
            option_text=opt.option_text,
            option_image_url=opt.option_image_url,
            is_correct=opt.is_correct,
            display_order=opt.display_order or i,
        ))

    db.commit()
    db.refresh(question)
    return question


def list_lesson_quiz_questions(db: Session, lesson_id: uuid.UUID) -> list[QuizQuestion]:
    return (
        db.query(QuizQuestion)
        .filter(QuizQuestion.lesson_id == lesson_id)
        .order_by(QuizQuestion.display_order)
        .all()
    )


def list_stage_quiz_questions(
    db: Session, journey_stage_id: uuid.UUID,
    department_type_id: uuid.UUID | None, department_type_is_general: bool,
    procedure_id: uuid.UUID | None = None,
) -> list[QuizQuestion]:
    query = db.query(QuizQuestion).filter(QuizQuestion.journey_stage_id == journey_stage_id)
    if department_type_is_general:
        query = query.filter(QuizQuestion.department_type_id.is_(None))
    elif department_type_id:
        query = query.filter(QuizQuestion.department_type_id == department_type_id)

    if procedure_id:
        query = query.filter(QuizQuestion.procedure_id == procedure_id)
    else:
        query = query.filter(QuizQuestion.procedure_id.is_(None))

    return query.order_by(QuizQuestion.display_order).all()


def delete_quiz_question(db: Session, question_id: uuid.UUID) -> None:
    question = db.query(QuizQuestion).filter(QuizQuestion.id == question_id).first()
    if not question:
        raise ContentNotFoundError("سوال پیدا نشد.")
    db.delete(question)
    db.commit()