# app/services/ghost_session_service.py
"""
app/services/ghost_session_service.py

Creates, lists, re-enters, force-jumps, and deletes "ghost" patient
sessions - a super_admin QA tool for browsing any hospital/
department's patient-facing content exactly as a real patient would,
with zero content restrictions.

A ghost session is a REAL PatientAccessProfile (flagged is_ghost=True)
that gets the exact same signed profile cookie a real patient gets
(see app/services/access_gate_service.py) - after entering, the admin
is routed through the exact same production routes/templates a real
patient hits. Two deliberate bypasses exist ONLY for is_ghost rows:
  1. journey-stage lock (see content_targeting_service.get_journey_timeline)
     is fully open, regardless of lesson-completion progress.
  2. force_jump_stage() writes current_stage directly, bypassing
     patient_journey_state_machine.ALLOWED_TRANSITIONS entirely - a
     real patient can never skip stages out of order, but a QA ghost
     needs to reach any stage instantly.

Ghost profiles are excluded from every patient-facing analytics/
report query - see the is_ghost filters in admin_patient_report.py
and patient_monitoring_service.py.

delete_ghost_session() clears EVERY table that carries a FK pointing
at patient_access_profiles.id before deleting the profile row itself
- otherwise Postgres raises a ForeignKeyViolation, which previously
surfaced to the admin panel as an unhandled 500 ("خطای ناشناخته")
instead of a clean, catchable error. Tables covered: QuizAttempt,
FavoriteRecord, ProgressRecord, FeedbackRecord, FollowUpTask (deleted),
PatientReferral (detached, not deleted - it's real referral data),
PatientProcedureSelection, PatientJourneyProfile, PatientRegistration.
"""

import uuid
from datetime import datetime

from fastapi import Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.csrf import issue_csrf_cookie
from app.infrastructure.db.models import (
    PatientAccessProfile, PatientRegistration, PatientJourneyProfile,
    JourneyStageCode, Hospital, Department, Procedure,
    ProgressRecord, FavoriteRecord, QuizAttempt, FeedbackRecord,
    FollowUpTask, PatientReferral, PatientProcedureSelection,
)
from app.services import access_gate_service

GHOST_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 30  # 30 days - a QA tool session, not a real 180-day patient one


class GhostSessionError(Exception):
    pass


def _make_synthetic_national_id(profile_id: uuid.UUID) -> str:
    # Not a real 10-digit national ID and never needs to validate as
    # one - this row only exists so /profile also renders correctly
    # in ghost mode, exactly like a real patient's page.
    return f"ghost-{profile_id.hex[:12]}"


def create_ghost_session(
    db: Session,
    admin_id: uuid.UUID,
    hospital_id: uuid.UUID,
    department_id: uuid.UUID,
    ghost_label: str | None,
    disease_id: uuid.UUID | None,
    treatment_id: uuid.UUID | None,
    procedure_id: uuid.UUID | None,
    has_surgery: bool | None,
    age: int | None,
    gender: str | None,
    target_stage_code: str | None,
) -> PatientAccessProfile:
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise GhostSessionError("بیمارستان پیدا نشد.")

    department = (
        db.query(Department)
        .filter(Department.id == department_id, Department.hospital_id == hospital_id)
        .first()
    )
    if not department:
        raise GhostSessionError("بخش پیدا نشد یا به این بیمارستان تعلق ندارد.")

    if procedure_id:
        procedure = db.query(Procedure).filter(Procedure.id == procedure_id).first()
        if not procedure or procedure.department_type_id != department.department_type_id:
            raise GhostSessionError("این عمل متعلق به این بخش نیست.")

    profile = PatientAccessProfile(
        hospital_id=hospital_id,
        department_id=department_id,
        is_ghost=True,
        ghost_created_by_admin_id=admin_id,
        ghost_label=(ghost_label or "").strip()[:255] or None,
    )
    db.add(profile)
    db.flush()

    db.add(PatientRegistration(
        patient_access_profile_id=profile.id,
        first_name="بازدید کننده",
        last_name="(نشست QA ادمین)",
        national_id=_make_synthetic_national_id(profile.id),
        phone_number="00000000000",
        insurance_code=None,
    ))

    try:
        target_stage = JourneyStageCode(target_stage_code) if target_stage_code else JourneyStageCode.WELCOME
    except ValueError:
        target_stage = JourneyStageCode.WELCOME

    db.add(PatientJourneyProfile(
        patient_access_profile_id=profile.id,
        disease_id=disease_id,
        treatment_id=treatment_id,
        procedure_id=procedure_id,
        has_surgery=has_surgery,
        age=age,
        gender=gender,
        current_stage=target_stage,
        onboarding_completed_at=datetime.utcnow(),
    ))

    db.commit()
    db.refresh(profile)
    return profile


def list_ghost_sessions(db: Session) -> list[PatientAccessProfile]:
    return (
        db.query(PatientAccessProfile)
        .filter(PatientAccessProfile.is_ghost.is_(True))
        .order_by(PatientAccessProfile.first_seen_at.desc())
        .all()
    )


def get_ghost_session_or_raise(db: Session, ghost_profile_id: uuid.UUID) -> PatientAccessProfile:
    profile = (
        db.query(PatientAccessProfile)
        .filter(PatientAccessProfile.id == ghost_profile_id, PatientAccessProfile.is_ghost.is_(True))
        .first()
    )
    if not profile:
        raise GhostSessionError("این نشست حالت روح پیدا نشد.")
    return profile


def force_jump_stage(db: Session, ghost_profile_id: uuid.UUID, target_stage_code: str) -> PatientJourneyProfile:
    profile = get_ghost_session_or_raise(db, ghost_profile_id)

    try:
        target_stage = JourneyStageCode(target_stage_code)
    except ValueError:
        raise GhostSessionError("کد مرحله نامعتبر است.")

    journey = (
        db.query(PatientJourneyProfile)
        .filter(
            PatientJourneyProfile.patient_access_profile_id == profile.id,
            PatientJourneyProfile.is_active.is_(True),
        )
        .order_by(PatientJourneyProfile.created_at.desc())
        .first()
    )
    if not journey:
        raise GhostSessionError("مسیر درمانی این نشست پیدا نشد.")

    journey.current_stage = target_stage
    db.commit()
    db.refresh(journey)
    return journey


def enter_ghost_session_cookies(response: Response, profile_id: uuid.UUID) -> None:
    response.set_cookie(
        key=settings.PATIENT_PROFILE_COOKIE_NAME,
        value=access_gate_service.sign_profile_cookie(profile_id),
        max_age=GHOST_COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
    )
    issue_csrf_cookie(response, settings.CSRF_COOKIE_NAME)
    response.set_cookie(
        key=settings.GHOST_MODE_COOKIE_NAME,
        value="1",
        max_age=GHOST_COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
    )


def exit_ghost_session_cookies(response: Response) -> None:
    response.delete_cookie(settings.PATIENT_PROFILE_COOKIE_NAME)
    response.delete_cookie(settings.CSRF_COOKIE_NAME)
    response.delete_cookie(settings.GHOST_MODE_COOKIE_NAME)


def delete_ghost_session(db: Session, ghost_profile_id: uuid.UUID) -> None:
    profile = get_ghost_session_or_raise(db, ghost_profile_id)

    db.query(QuizAttempt).filter(QuizAttempt.patient_access_profile_id == profile.id).delete(synchronize_session=False)
    db.query(FavoriteRecord).filter(FavoriteRecord.patient_access_profile_id == profile.id).delete(synchronize_session=False)
    db.query(ProgressRecord).filter(ProgressRecord.patient_access_profile_id == profile.id).delete(synchronize_session=False)
    db.query(FeedbackRecord).filter(FeedbackRecord.patient_access_profile_id == profile.id).delete(synchronize_session=False)
    db.query(FollowUpTask).filter(FollowUpTask.patient_access_profile_id == profile.id).delete(synchronize_session=False)
    db.query(PatientProcedureSelection).filter(
        PatientProcedureSelection.patient_access_profile_id == profile.id
    ).delete(synchronize_session=False)
    db.query(PatientReferral).filter(PatientReferral.patient_access_profile_id == profile.id).update(
        {PatientReferral.patient_access_profile_id: None}, synchronize_session=False
    )
    db.query(PatientJourneyProfile).filter(PatientJourneyProfile.patient_access_profile_id == profile.id).delete(synchronize_session=False)
    db.query(PatientRegistration).filter(PatientRegistration.patient_access_profile_id == profile.id).delete(synchronize_session=False)

    db.delete(profile)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise GhostSessionError(f"حذف نشست روح ممکن نشد: {exc.orig}") from exc