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
Operating-room-related education now lives in BEFORE_PROCEDURE.

PROCEDURE_INTRO ("آشنایی با عمل", see migration 9a1c5e7f2b4d) sits
between ADMISSION and BEFORE_PROCEDURE: once the patient/nurse has
picked a specific procedure during onboarding (procedure_id, always
scoped to the patient's own department_type - see onboarding.py /
patient_self_auth.py), the patient lands here first to read
procedure-specific content before the general pre-operation
preparation content in BEFORE_PROCEDURE.
"""

import uuid

from sqlalchemy.orm import Session

from app.core.event_bus import event_bus
from app.core.events import PatientStageChanged, PatientDischarged
from app.infrastructure.db.models import PatientJourneyProfile, JourneyStageCode
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class InvalidStageTransitionError(Exception):
    pass


ALLOWED_TRANSITIONS: dict[JourneyStageCode, list[JourneyStageCode]] = {
    JourneyStageCode.WELCOME: [
        JourneyStageCode.ADMISSION,
        JourneyStageCode.PROCEDURE_INTRO,
        JourneyStageCode.BEFORE_PROCEDURE,
    ],
    JourneyStageCode.ADMISSION: [
        JourneyStageCode.PROCEDURE_INTRO,
        JourneyStageCode.BEFORE_PROCEDURE,
        JourneyStageCode.DAILY_INPATIENT,
        JourneyStageCode.DISCHARGE,
    ],
    JourneyStageCode.PROCEDURE_INTRO: [
        JourneyStageCode.BEFORE_PROCEDURE,
        JourneyStageCode.DAILY_INPATIENT,
    ],
    JourneyStageCode.BEFORE_PROCEDURE: [
        JourneyStageCode.AFTER_PROCEDURE,
        JourneyStageCode.DAILY_INPATIENT,
    ],
    JourneyStageCode.AFTER_PROCEDURE: [
        JourneyStageCode.DAILY_INPATIENT,
        JourneyStageCode.DISCHARGE,
    ],
    JourneyStageCode.DAILY_INPATIENT: [
        JourneyStageCode.DISCHARGE,
    ],
    JourneyStageCode.DISCHARGE: [
        JourneyStageCode.HOME_CARE,
    ],
    JourneyStageCode.HOME_CARE: [
        JourneyStageCode.FOLLOW_UP,
    ],
    JourneyStageCode.FOLLOW_UP: [
        JourneyStageCode.LONG_TERM_MONITORING,
    ],
    JourneyStageCode.LONG_TERM_MONITORING: [],
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