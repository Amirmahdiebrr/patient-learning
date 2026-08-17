"""
app/services/content_admin/smart_import_commit_service.py
"""

from app.core.sanitize import sanitize_html
from app.infrastructure.db.models import (
    JourneyStage, JourneyStageCode, StandardDepartmentType,
    EducationSection, Lesson, LessonOverrideLevel,
    QuizQuestion, QuizOption, QuizAttempt,
)
from app.schemas.content_bulk_import import SmartImportCommitPayload, RawQuizQuestionImportItem


def _resolve_journey_stage(db, code: str) -> JourneyStage | None:
    try:
        stage_code = JourneyStageCode(code.strip().lower())
    except ValueError:
        return None
    return db.query(JourneyStage).filter(JourneyStage.code == stage_code).first()


def _resolve_department_type(db, code: str | None):
    if not code or code.strip().lower() == "general":
        return None, True
    dept_type = db.query(StandardDepartmentType).filter(StandardDepartmentType.code == code.strip()).first()
    return dept_type, dept_type is not None


def _find_or_create_section(db, journey_stage: JourneyStage, department_type_id, title: str):
    existing = (
        db.query(EducationSection)
        .filter(
            EducationSection.journey_stage_id == journey_stage.id,
            EducationSection.department_type_id == department_type_id,
            EducationSection.title == title,
        )
        .first()
    )
    if existing:
        return existing, False

    section = EducationSection(
        journey_stage_id=journey_stage.id,
        department_type_id=department_type_id,
        title=title,
        display_order=0,
    )
    db.add(section)
    db.flush()
    return section, True


def _find_or_create_lesson(db, section: EducationSection, title: str, body: str | None, is_published: bool):
    existing = (
        db.query(Lesson)
        .filter(
            Lesson.section_id == section.id,
            Lesson.title == title,
            Lesson.override_level == LessonOverrideLevel.GLOBAL,
        )
        .first()
    )
    if existing:
        existing.body_richtext = sanitize_html(body)
        existing.is_published = is_published
        db.flush()
        return existing, False

    lesson = Lesson(
        section_id=section.id,
        title=title,
        body_richtext=sanitize_html(body),
        display_order=0,
        is_published=is_published,
        override_level=LessonOverrideLevel.GLOBAL,
    )
    db.add(lesson)
    db.flush()
    return lesson, True


def _replace_quiz_questions(db, lesson: Lesson, quiz_questions: list[RawQuizQuestionImportItem]) -> int:
    existing_question_ids = [
        row[0] for row in db.query(QuizQuestion.id).filter(QuizQuestion.lesson_id == lesson.id).all()
    ]
    if existing_question_ids:
        db.query(QuizAttempt).filter(QuizAttempt.question_id.in_(existing_question_ids)).delete(synchronize_session=False)
        db.query(QuizQuestion).filter(QuizQuestion.id.in_(existing_question_ids)).delete(synchronize_session=False)
        db.flush()

    created = 0
    for q in quiz_questions:
        question = QuizQuestion(
            lesson_id=lesson.id,
            question_text=q.question_text,
            question_image_url=q.question_image_url,
            display_order=created,
        )
        db.add(question)
        db.flush()

        for i, opt in enumerate(q.options):
            db.add(QuizOption(
                question_id=question.id,
                option_text=opt.option_text,
                option_image_url=opt.option_image_url,
                is_correct=opt.is_correct,
                display_order=i,
            ))
        created += 1

    return created


def run_smart_import_commit(db, payload: SmartImportCommitPayload) -> dict:
    summary = {
        "sections_created": 0, "sections_reused": 0,
        "lessons_created": 0, "lessons_updated": 0,
        "quiz_questions_created": 0,
        "errors": [],
    }

    for item in payload.items:
        journey_stage = _resolve_journey_stage(db, item.journey_stage_code)
        if not journey_stage:
            summary["errors"].append(f"درس «{item.title}»: مرحله‌ی سفر بیمار نامعتبر است.")
            continue

        dept_type, dept_ok = _resolve_department_type(db, item.department_type_code)
        if not dept_ok:
            summary["errors"].append(f"درس «{item.title}»: نوع بخش پیدا نشد.")
            continue

        section, section_created = _find_or_create_section(
            db, journey_stage, dept_type.id if dept_type else None, item.section_title,
        )
        summary["sections_created" if section_created else "sections_reused"] += 1

        lesson, lesson_created = _find_or_create_lesson(db, section, item.title, item.body, item.is_published)
        summary["lessons_created" if lesson_created else "lessons_updated"] += 1

        if item.quiz_questions:
            summary["quiz_questions_created"] += _replace_quiz_questions(db, lesson, item.quiz_questions)

    db.commit()
    return summary