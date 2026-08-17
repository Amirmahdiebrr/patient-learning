"""
app/services/content_targeting_service.py

Resolves published lessons AND stage-level quiz questions for a
patient journey.

Lessons: structural match (journey_stage + department_type) with
hospital-level override resolution and optional ContentTargetingRule
filtering - see get_lessons_for_stage.

get_journey_timeline() builds the patient's home-page journey view:
every JourneyStage up to and including the patient's current stage
(ordered by JourneyStage.display_order), each carrying its own
lessons AND its own stage-level quiz (quiz now lives inside its
stage, not as a separate page-wide block). A stage is "completed"
once every one of its lessons has a COMPLETED ProgressRecord for this
patient; a stage is "unlocked" once the previous stage in the
timeline is completed (the first stage is always unlocked). The
template uses is_completed/is_unlocked to gate access - later stages
stay collapsed/locked until the patient has actually gone through the
earlier ones.

Stage quiz resolution has no hospital-override or targeting-rule
layer (not requested / not needed yet) - keep it simple until a real
need for per-hospital quiz overrides shows up.
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
    JourneyStage,
    JourneyStageCode,
    ProgressRecord,
    LessonProgressStatus,
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


def get_lessons_for_stage(
    db: Session,
    journey: PatientJourneyProfile,
    stage_code: JourneyStageCode,
    hospital_id: uuid.UUID,
    department_id: uuid.UUID,
    department_type_id: uuid.UUID | None,
) -> list[Lesson]:
    sections = (
        db.query(EducationSection)
        .filter(
            EducationSection.journey_stage.has(code=stage_code),
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


def get_lessons_for_journey(
    db: Session,
    journey: PatientJourneyProfile,
    hospital_id: uuid.UUID,
    department_id: uuid.UUID,
    department_type_id: uuid.UUID | None,
) -> list[Lesson]:
    return get_lessons_for_stage(
        db, journey, journey.current_stage, hospital_id, department_id, department_type_id
    )


def get_stage_quiz_for_stage(
    db: Session,
    stage_code: JourneyStageCode,
    department_type_id: uuid.UUID | None,
) -> list[QuizQuestion]:
    return (
        db.query(QuizQuestion)
        .filter(
            QuizQuestion.journey_stage.has(code=stage_code),
            or_(
                QuizQuestion.department_type_id.is_(None),
                QuizQuestion.department_type_id == department_type_id,
            ),
        )
        .order_by(QuizQuestion.display_order)
        .all()
    )


def get_stage_quiz_for_journey(
    db: Session,
    journey: PatientJourneyProfile,
    department_type_id: uuid.UUID | None,
) -> list[QuizQuestion]:
    return get_stage_quiz_for_stage(db, journey.current_stage, department_type_id)


def get_journey_timeline(
    db: Session,
    journey: PatientJourneyProfile,
    patient_access_profile_id: uuid.UUID,
    hospital_id: uuid.UUID,
    department_id: uuid.UUID,
    department_type_id: uuid.UUID | None,
) -> list[dict]:
    """
    Ordered "journey so far" view for the patient home page: one
    entry per JourneyStage with display_order <= the patient's
    current stage, each with its own lessons (+ completion state) and
    its own stage-level quiz. A stage with neither lessons nor quiz
    questions is skipped entirely.
    """
    current_stage_row = db.query(JourneyStage).filter(JourneyStage.code == journey.current_stage).first()
    if not current_stage_row:
        return []

    stages = (
        db.query(JourneyStage)
        .filter(JourneyStage.display_order <= current_stage_row.display_order)
        .order_by(JourneyStage.display_order)
        .all()
    )

    timeline: list[dict] = []
    previous_completed = True  # the first visible stage is always unlocked

    for stage in stages:
        lessons = get_lessons_for_stage(db, journey, stage.code, hospital_id, department_id, department_type_id)
        quiz_questions = get_stage_quiz_for_stage(db, stage.code, department_type_id)

        if not lessons and not quiz_questions:
            continue

        completed_lesson_ids: set[uuid.UUID] = set()
        if lessons:
            lesson_ids = [l.id for l in lessons]
            completed_lesson_ids = {
                row[0] for row in db.query(ProgressRecord.lesson_id).filter(
                    ProgressRecord.patient_access_profile_id == patient_access_profile_id,
                    ProgressRecord.lesson_id.in_(lesson_ids),
                    ProgressRecord.status == LessonProgressStatus.COMPLETED,
                ).all()
            }

        lessons_with_status = [
            {"lesson": lesson, "is_completed": lesson.id in completed_lesson_ids}
            for lesson in lessons
        ]

        stage_completed = bool(lessons) and len(completed_lesson_ids) == len(lessons)
        stage_unlocked = previous_completed

        timeline.append({
            "stage_code": stage.code.value,
            "stage_name": stage.name,
            "is_current": stage.code == journey.current_stage,
            "is_completed": stage_completed,
            "is_unlocked": stage_unlocked,
            "lessons": lessons_with_status,
            "quiz_questions": quiz_questions,
        })

        previous_completed = stage_completed if stage_unlocked else False

    return timeline