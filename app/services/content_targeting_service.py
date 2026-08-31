# app/services/content_targeting_service.py
"""
app/services/content_targeting_service.py

Resolves published lessons AND stage-level quiz questions for a
patient journey.

Resolution layers, most to least specific:
  1. Hospital-level lesson override (Lesson.override_level=HOSPITAL)
  2. Procedure-specific content (EducationSection.procedure_id /
     QuizQuestion.procedure_id matches ANY of the patient's effective
     procedure ids - see patient_procedure_service.get_effective_procedure_ids,
     which unions their onboarding procedure_id with whatever they've
     explicitly picked from their own profile via /my-procedures)
  3. Department-general content (procedure_id IS NULL)
  4. Global content (department_type_id IS NULL)

Layers 2/3 are an OVERRIDE, not a merge: for a given
(journey_stage, department_type) combination, if the patient has any
effective procedure ids AND at least one section/quiz exists scoped
to any of them, ONLY those (unioned across all matching procedures)
are shown; otherwise the department-general ones are used. This
mirrors the existing hospital-override pattern and needs no AI -
matching is purely by department_type_id/procedure_id/journey_stage
foreign keys.

get_stage_completion() is the SINGLE SOURCE OF TRUTH for "is this
stage's content fully done for this patient" - every lesson has a
COMPLETED ProgressRecord AND every stage-level quiz question has at
least one QuizAttempt. Both get_journey_timeline() (for the lock/badge
UI) and patient_journey_state_machine.try_auto_advance_stage() (for
whether to move current_stage forward) call this exact same function.

get_journey_timeline() builds the patient's home-page SEQUENTIAL,
LOCKED journey view. WELCOME's generic hospital-wide lesson is
excluded (shown once on /home hero instead). PROCEDURE_INTRO /
BEFORE_PROCEDURE / AFTER_PROCEDURE are excluded entirely - they are
never locked and never gate progression (see
patient_journey_state_machine.OPTIONAL_SURGERY_STAGES); their content
is resolved instead by get_surgery_education_groups() and rendered on
the dedicated /my-surgery-education page.

get_patient_lesson_library() is a flat, searchable/filterable view
over the exact same already-resolved, already-authorized content:
every lesson in an UNLOCKED main-journey stage plus every lesson in
the surgery-education groups. It introduces no new content-resolution
rule - it just re-shapes get_journey_timeline +
get_surgery_education_groups output for the /my-lessons library page.

GHOST MODE EXCEPTION: if patient_access_profile_id belongs to a ghost
profile (PatientAccessProfile.is_ghost=True), every stage in the
timeline is treated as unlocked regardless of completion state.
"""

import uuid

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.infrastructure.db.models import (
    Lesson,
    EducationSection,
    ContentTargetingRule,
    PatientJourneyProfile,
    PatientAccessProfile,
    LessonOverrideLevel,
    QuizQuestion,
    QuizAttempt,
    JourneyStage,
    JourneyStageCode,
    ProgressRecord,
    LessonProgressStatus,
)
from app.services.patient_procedure_service import get_effective_procedure_ids

_OPTIONAL_SURGERY_STAGES = {
    JourneyStageCode.PROCEDURE_INTRO,
    JourneyStageCode.BEFORE_PROCEDURE,
    JourneyStageCode.AFTER_PROCEDURE,
}

_SURGERY_EDUCATION_STAGE_LABELS: list[tuple[JourneyStageCode, str]] = [
    (JourneyStageCode.PROCEDURE_INTRO, "آشنایی با عمل"),
    (JourneyStageCode.BEFORE_PROCEDURE, "قبل از عمل"),
    (JourneyStageCode.AFTER_PROCEDURE, "بعد از عمل"),
]


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


def _sections_for_stage(
    db: Session,
    stage_code: JourneyStageCode,
    department_type_id: uuid.UUID | None,
    treatment_id: uuid.UUID | None,
    procedure_filter,
) -> list[EducationSection]:
    return (
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
                EducationSection.treatment_id == treatment_id,
            ),
            procedure_filter,
        )
        .order_by(EducationSection.display_order)
        .all()
    )


def _resolve_sections(
    db: Session,
    stage_code: JourneyStageCode,
    department_type_id: uuid.UUID | None,
    treatment_id: uuid.UUID | None,
    procedure_ids: list[uuid.UUID] | None,
) -> list[EducationSection]:
    if procedure_ids:
        procedure_sections = _sections_for_stage(
            db, stage_code, department_type_id, treatment_id,
            EducationSection.procedure_id.in_(procedure_ids),
        )
        if procedure_sections:
            return procedure_sections

    return _sections_for_stage(
        db, stage_code, department_type_id, treatment_id,
        EducationSection.procedure_id.is_(None),
    )


def get_lessons_for_stage(
    db: Session,
    journey: PatientJourneyProfile,
    stage_code: JourneyStageCode,
    hospital_id: uuid.UUID,
    department_id: uuid.UUID,
    department_type_id: uuid.UUID | None,
    procedure_ids: list[uuid.UUID] | None = None,
) -> list[Lesson]:
    sections = _resolve_sections(db, stage_code, department_type_id, journey.treatment_id, procedure_ids)

    matched_lessons: list[Lesson] = []
    seen_lesson_ids: set[uuid.UUID] = set()

    for section in sections:
        for lesson in section.lessons:
            if lesson.override_level == LessonOverrideLevel.HOSPITAL:
                continue

            effective_lesson = _resolve_effective_lesson(db, lesson, hospital_id)
            if effective_lesson is None:
                continue

            matched = False
            if not lesson.targeting_rules:
                matched = True
            elif any(
                _rule_matches(rule, journey, hospital_id, department_id)
                for rule in lesson.targeting_rules
            ):
                matched = True

            if matched and effective_lesson.id not in seen_lesson_ids:
                matched_lessons.append(effective_lesson)
                seen_lesson_ids.add(effective_lesson.id)

    return matched_lessons


def get_lessons_for_journey(
    db: Session,
    journey: PatientJourneyProfile,
    hospital_id: uuid.UUID,
    department_id: uuid.UUID,
    department_type_id: uuid.UUID | None,
) -> list[Lesson]:
    procedure_ids = get_effective_procedure_ids(db, journey)
    return get_lessons_for_stage(
        db, journey, journey.current_stage, hospital_id, department_id, department_type_id,
        procedure_ids=procedure_ids,
    )


def _quiz_for_stage(
    db: Session,
    stage_code: JourneyStageCode,
    department_type_id: uuid.UUID | None,
    procedure_filter,
) -> list[QuizQuestion]:
    return (
        db.query(QuizQuestion)
        .filter(
            QuizQuestion.journey_stage.has(code=stage_code),
            or_(
                QuizQuestion.department_type_id.is_(None),
                QuizQuestion.department_type_id == department_type_id,
            ),
            procedure_filter,
        )
        .order_by(QuizQuestion.display_order)
        .all()
    )


def get_stage_quiz_for_stage(
    db: Session,
    stage_code: JourneyStageCode,
    department_type_id: uuid.UUID | None,
    procedure_ids: list[uuid.UUID] | None = None,
) -> list[QuizQuestion]:
    if procedure_ids:
        procedure_questions = _quiz_for_stage(
            db, stage_code, department_type_id, QuizQuestion.procedure_id.in_(procedure_ids),
        )
        if procedure_questions:
            return procedure_questions

    return _quiz_for_stage(db, stage_code, department_type_id, QuizQuestion.procedure_id.is_(None))


def get_stage_quiz_for_journey(
    db: Session,
    journey: PatientJourneyProfile,
    department_type_id: uuid.UUID | None,
) -> list[QuizQuestion]:
    procedure_ids = get_effective_procedure_ids(db, journey)
    return get_stage_quiz_for_stage(db, journey.current_stage, department_type_id, procedure_ids=procedure_ids)


def get_stage_completion(
    db: Session,
    patient_access_profile_id: uuid.UUID,
    lessons: list[Lesson],
    quiz_questions: list[QuizQuestion],
) -> tuple[bool, set[uuid.UUID]]:
    if not lessons and not quiz_questions:
        return False, set()

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
        if len(completed_lesson_ids) < len(lesson_ids):
            return False, completed_lesson_ids

    if quiz_questions:
        question_ids = [q.id for q in quiz_questions]
        answered_ids = {
            row[0] for row in db.query(QuizAttempt.question_id).filter(
                QuizAttempt.patient_access_profile_id == patient_access_profile_id,
                QuizAttempt.question_id.in_(question_ids),
            ).distinct().all()
        }
        if len(answered_ids) < len(question_ids):
            return False, completed_lesson_ids

    return True, completed_lesson_ids


def get_journey_timeline(
    db: Session,
    journey: PatientJourneyProfile,
    patient_access_profile_id: uuid.UUID,
    hospital_id: uuid.UUID,
    department_id: uuid.UUID,
    department_type_id: uuid.UUID | None,
) -> list[dict]:
    current_stage_row = db.query(JourneyStage).filter(JourneyStage.code == journey.current_stage).first()
    if not current_stage_row:
        return []

    stages = (
        db.query(JourneyStage)
        .filter(
            JourneyStage.display_order <= current_stage_row.display_order,
            JourneyStage.code.notin_(_OPTIONAL_SURGERY_STAGES),
        )
        .order_by(JourneyStage.display_order)
        .all()
    )

    procedure_ids = get_effective_procedure_ids(db, journey)

    is_ghost_profile = bool(
        db.query(PatientAccessProfile.is_ghost)
        .filter(PatientAccessProfile.id == patient_access_profile_id)
        .scalar()
    )

    timeline: list[dict] = []
    previous_completed = True

    for stage in stages:
        lessons = get_lessons_for_stage(
            db, journey, stage.code, hospital_id, department_id, department_type_id,
            procedure_ids=procedure_ids,
        )

        if stage.code == JourneyStageCode.WELCOME:
            lessons = [l for l in lessons if l.section.department_type_id is not None]

        quiz_questions = get_stage_quiz_for_stage(db, stage.code, department_type_id, procedure_ids=procedure_ids)

        if not lessons and not quiz_questions:
            continue

        stage_completed, completed_lesson_ids = get_stage_completion(
            db, patient_access_profile_id, lessons, quiz_questions,
        )

        lessons_with_status = [
            {"lesson": lesson, "is_completed": lesson.id in completed_lesson_ids}
            for lesson in lessons
        ]

        stage_unlocked = True if is_ghost_profile else previous_completed

        timeline.append({
            "stage_code": stage.code.value,
            "stage_name": stage.name,
            "is_current": stage.code == journey.current_stage,
            "is_completed": stage_completed,
            "is_unlocked": stage_unlocked,
            "lessons": lessons_with_status,
            "quiz_questions": quiz_questions,
        })

        previous_completed = True if is_ghost_profile else (stage_completed if stage_unlocked else False)

    return timeline


def get_surgery_education_groups(
    db: Session,
    journey: PatientJourneyProfile,
    patient_access_profile_id: uuid.UUID,
    hospital_id: uuid.UUID,
    department_id: uuid.UUID,
    department_type_id: uuid.UUID | None,
) -> list[dict]:
    procedure_ids = get_effective_procedure_ids(db, journey)

    groups: list[dict] = []
    for stage_code, label in _SURGERY_EDUCATION_STAGE_LABELS:
        lessons = get_lessons_for_stage(
            db, journey, stage_code, hospital_id, department_id, department_type_id,
            procedure_ids=procedure_ids,
        )
        quiz_questions = get_stage_quiz_for_stage(db, stage_code, department_type_id, procedure_ids=procedure_ids)

        if not lessons and not quiz_questions:
            continue

        _, completed_lesson_ids = get_stage_completion(db, patient_access_profile_id, lessons, quiz_questions)

        lessons_with_status = [
            {"lesson": lesson, "is_completed": lesson.id in completed_lesson_ids}
            for lesson in lessons
        ]

        groups.append({
            "stage_code": stage_code.value,
            "stage_name": label,
            "lessons": lessons_with_status,
            "quiz_questions": quiz_questions,
        })

    return groups


def get_patient_lesson_library(
    db: Session,
    journey: PatientJourneyProfile,
    patient_access_profile_id: uuid.UUID,
    hospital_id: uuid.UUID,
    department_id: uuid.UUID,
    department_type_id: uuid.UUID | None,
) -> list[dict]:
    """
    Flat, browsable list of every lesson currently accessible to the
    patient: every lesson in an UNLOCKED main-journey stage (locked
    future stages excluded) plus every lesson in the always-optional
    surgery-education groups. Backs the /my-lessons search/filter
    library page - purely a different presentation of data the
    patient could already reach through /home and
    /my-surgery-education; no new content-resolution rules.
    """
    items: list[dict] = []

    timeline = get_journey_timeline(
        db, journey, patient_access_profile_id,
        hospital_id, department_id, department_type_id,
    )
    for stage in timeline:
        if not stage["is_unlocked"]:
            continue
        for entry in stage["lessons"]:
            lesson = entry["lesson"]
            items.append({
                "lesson": lesson,
                "stage_code": stage["stage_code"],
                "stage_name": stage["stage_name"],
                "is_completed": entry["is_completed"],
                "media_types": sorted({m.type.value for m in lesson.media_assets}),
                "has_quiz": bool(lesson.quiz_questions),
            })

    surgery_groups = get_surgery_education_groups(
        db, journey, patient_access_profile_id,
        hospital_id, department_id, department_type_id,
    )
    for group in surgery_groups:
        for entry in group["lessons"]:
            lesson = entry["lesson"]
            items.append({
                "lesson": lesson,
                "stage_code": group["stage_code"],
                "stage_name": group["stage_name"],
                "is_completed": entry["is_completed"],
                "media_types": sorted({m.type.value for m in lesson.media_assets}),
                "has_quiz": bool(lesson.quiz_questions),
            })

    return items