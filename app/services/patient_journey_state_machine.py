# app/services/patient_journey_state_machine.py
# app/services/patient_journey_state_machine.py
"""
app/services/patient_journey_state_machine.py

Explicit rule-based state machine for PatientJourneyProfile.current_stage.
ALLOWED_TRANSITIONS is the single source of truth - callers never
hardcode stage logic.

NOTE: GENERAL_EDUCATION/DEPARTMENT_INTRO (merged into ADMISSION, see
migration 6c4f2b8e9a1d) and PROCEDURE ("حین عمل", merged into
BEFORE_PROCEDURE, see migration 7c4e9a2f1b6d) no longer appear as
selectable journey_stages rows, so no transitions reference them.

PROCEDURE_INTRO / BEFORE_PROCEDURE / AFTER_PROCEDURE ("آشنایی با عمل" /
"قبل از عمل" / "بعد از عمل") are NOT part of the sequential main
journey. They are a separate, always-optional "surgery education"
section reached via its own sub-nav (see
app/templates/patient_surgery_subnav.html and
app/api/v1/patient_procedures.py::my_surgery_education_page) - resolved
by content_targeting_service.get_surgery_education_groups with no
lock and no effect on current_stage whatsoever.

The main sequential flow is: WELCOME -> ADMISSION -> DAILY_INPATIENT
-> DISCHARGE -> HOME_CARE (linear, no branching).

FOLLOW_UP and LONG_TERM_MONITORING were merged into HOME_CARE, renamed
"پیگیری و مراقبت در منزل" (see migration f1a4c7e9b2d6) - HOME_CARE is
the final stage (no outgoing transitions).

AUTOMATIC STAGE ADVANCEMENT (try_auto_advance_stage):
Called after every lesson-completion and every quiz-attempt event (see
patient_lessons.py). It checks whether the patient's CURRENT stage is
fully done via content_targeting_service.get_stage_completion - the
EXACT SAME function get_journey_timeline uses for its lock/badge state,
so the UI and the transition decision can never disagree about whether
a stage is "done" (a previous version had two separate, slightly
different checks, which could leave a patient stuck on a stage the UI
already showed as "تکمیل‌شده"). If complete, it walks forward through
ALLOWED_TRANSITIONS - possibly across several hops, since the linear
flow above normally has exactly one candidate at each step - to find
the next stage that actually has content for this patient, skipping
any empty stage entirely. Applies identically to real patients and to
ghost sessions.
"""

import uuid

from sqlalchemy.orm import Session

from app.core.event_bus import event_bus
from app.core.events import PatientStageChanged, PatientDischarged
from app.infrastructure.db.models import PatientJourneyProfile, JourneyStageCode, JourneyStage
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class InvalidStageTransitionError(Exception):
    pass


ALLOWED_TRANSITIONS: dict[JourneyStageCode, list[JourneyStageCode]] = {
    JourneyStageCode.WELCOME: [
        JourneyStageCode.ADMISSION,
    ],
    JourneyStageCode.ADMISSION: [
        JourneyStageCode.DAILY_INPATIENT,
        JourneyStageCode.DISCHARGE,
    ],
    JourneyStageCode.DAILY_INPATIENT: [
        JourneyStageCode.DISCHARGE,
    ],
    JourneyStageCode.DISCHARGE: [
        JourneyStageCode.HOME_CARE,
    ],
    JourneyStageCode.HOME_CARE: [],
    # PROCEDURE_INTRO / BEFORE_PROCEDURE / AFTER_PROCEDURE deliberately
    # absent - no longer reachable via the normal sequential flow (see
    # module docstring). A ghost session can still force_jump_stage()
    # into them directly (that bypasses this map entirely).
}

# Stages that live outside the sequential main flow entirely - see
# module docstring / content_targeting_service._OPTIONAL_SURGERY_STAGES.
OPTIONAL_SURGERY_STAGES: set[JourneyStageCode] = {
    JourneyStageCode.PROCEDURE_INTRO,
    JourneyStageCode.BEFORE_PROCEDURE,
    JourneyStageCode.AFTER_PROCEDURE,
}


def can_transition(current: JourneyStageCode, target: JourneyStageCode) -> bool:
    if current == target:
        return True
    return target in ALLOWED_TRANSITIONS.get(current, [])


def transition_stage(
    db: Session,
    journey: PatientJourneyProfile,
    target_stage: JourneyStageCode,
    hospital_id: uuid.UUID,
    triggered_by: str = "manual",
) -> PatientJourneyProfile:
    if journey.current_stage == target_stage:
        return journey

    if not can_transition(journey.current_stage, target_stage):
        raise InvalidStageTransitionError(
            f"انتقال از '{journey.current_stage.value}' به '{target_stage.value}' مجاز نیست."
        )

    old_stage = journey.current_stage.value
    journey.current_stage = target_stage
    db.commit()
    db.refresh(journey)

    event_bus.publish(PatientStageChanged(
        patient_access_profile_id=journey.patient_access_profile_id,
        journey_id=journey.id,
        old_stage=old_stage,
        new_stage=target_stage.value,
    ))

    logger.info(f"[JourneyStateMachine] {old_stage} -> {target_stage.value} ({triggered_by})")

    if target_stage == JourneyStageCode.DISCHARGE:
        event_bus.publish(PatientDischarged(
            patient_access_profile_id=journey.patient_access_profile_id,
            hospital_id=hospital_id,
        ))

    return journey


def _stage_has_content(
    db: Session,
    journey: PatientJourneyProfile,
    stage_code: JourneyStageCode,
    hospital_id: uuid.UUID,
    department_id: uuid.UUID,
    department_type_id: uuid.UUID | None,
    procedure_ids: list[uuid.UUID],
) -> bool:
    from app.services.content_targeting_service import get_lessons_for_stage, get_stage_quiz_for_stage

    lessons = get_lessons_for_stage(
        db, journey, stage_code, hospital_id, department_id, department_type_id,
        procedure_ids=procedure_ids,
    )
    if stage_code == JourneyStageCode.WELCOME:
        lessons = [l for l in lessons if l.section.department_type_id is not None]

    if lessons:
        return True

    quiz_questions = get_stage_quiz_for_stage(db, stage_code, department_type_id, procedure_ids=procedure_ids)
    return bool(quiz_questions)


def _current_stage_complete(
    db: Session,
    journey: PatientJourneyProfile,
    patient_access_profile_id: uuid.UUID,
    hospital_id: uuid.UUID,
    department_id: uuid.UUID,
    department_type_id: uuid.UUID | None,
    procedure_ids: list[uuid.UUID],
) -> bool:
    from app.services.content_targeting_service import (
        get_lessons_for_stage, get_stage_quiz_for_stage, get_stage_completion,
    )

    stage_code = journey.current_stage
    lessons = get_lessons_for_stage(
        db, journey, stage_code, hospital_id, department_id, department_type_id,
        procedure_ids=procedure_ids,
    )
    if stage_code == JourneyStageCode.WELCOME:
        lessons = [l for l in lessons if l.section.department_type_id is not None]

    quiz_questions = get_stage_quiz_for_stage(db, stage_code, department_type_id, procedure_ids=procedure_ids)

    is_complete, _ = get_stage_completion(db, patient_access_profile_id, lessons, quiz_questions)
    return is_complete


def try_auto_advance_stage(
    db: Session,
    journey: PatientJourneyProfile,
    patient_access_profile_id: uuid.UUID,
    hospital_id: uuid.UUID,
    department_id: uuid.UUID,
    department_type_id: uuid.UUID | None,
) -> PatientJourneyProfile:
    """
    Advances journey.current_stage forward through ALLOWED_TRANSITIONS
    if (and only if) the CURRENT stage is fully done for this patient
    (see content_targeting_service.get_stage_completion). Walks
    forward through as many empty/no-content stages as needed to land
    on the next stage that actually has content, instead of stopping
    on - or getting stuck behind - a stage with nothing in it. Safe to
    call after every lesson-completion / quiz-attempt event; a no-op
    otherwise.
    """
    from app.services.patient_procedure_service import get_effective_procedure_ids

    if journey.current_stage == JourneyStageCode.HOME_CARE:
        return journey  # already the final stage

    procedure_ids = get_effective_procedure_ids(db, journey)

    if not _current_stage_complete(
        db, journey, patient_access_profile_id, hospital_id, department_id, department_type_id, procedure_ids,
    ):
        return journey

    stage_order_cache: dict[JourneyStageCode, int] = {
        s.code: s.display_order for s in db.query(JourneyStage).all()
    }

    def sorted_candidates(stage_code: JourneyStageCode) -> list[JourneyStageCode]:
        codes = ALLOWED_TRANSITIONS.get(stage_code, [])
        return sorted(codes, key=lambda c: stage_order_cache.get(c, 999))

    visited: set[JourneyStageCode] = {journey.current_stage}
    queue: list[JourneyStageCode] = sorted_candidates(journey.current_stage)

    target: JourneyStageCode | None = None
    fallback: JourneyStageCode | None = None

    while queue:
        code = queue.pop(0)
        if code in visited:
            continue
        visited.add(code)

        if fallback is None:
            fallback = code

        if _stage_has_content(
            db, journey, code, hospital_id, department_id, department_type_id, procedure_ids,
        ):
            target = code
            break

        queue.extend(sorted_candidates(code))

    if target is None:
        target = fallback

    if target is None:
        return journey

    return transition_stage(db, journey, target, hospital_id=hospital_id, triggered_by="automatic")