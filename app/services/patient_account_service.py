# app/services/patient_account_service.py
"""
app/services/patient_account_service.py

Permanently deletes a self-service patient's account: every row that
carries a FK to patient_access_profiles.id is removed (or, where the
row represents real hospital data rather than the patient's own
activity - e.g. a hospital referral - detached instead of deleted),
mirroring the exact same cascade pattern used for ghost sessions (see
ghost_session_service.delete_ghost_session). This is a hard, immediate,
irreversible delete requested by the patient themselves - there is no
soft-delete/undo period.
"""

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.infrastructure.db.models import (
    PatientAccessProfile, PatientRegistration, PatientJourneyProfile,
    ProgressRecord, FavoriteRecord, QuizAttempt, FeedbackRecord,
    FollowUpTask, PatientReferral, PatientProcedureSelection,
)


class PatientAccountDeletionError(Exception):
    pass


def delete_patient_account(db: Session, patient_access_profile_id: uuid.UUID) -> None:
    profile = (
        db.query(PatientAccessProfile)
        .filter(PatientAccessProfile.id == patient_access_profile_id)
        .first()
    )
    if not profile:
        raise PatientAccountDeletionError("حساب کاربری پیدا نشد.")

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
        raise PatientAccountDeletionError(f"حذف حساب کاربری ممکن نشد: {exc.orig}") from exc