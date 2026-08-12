"""
app/api/v1/admin_patient_journey.py

Manual patient-journey-stage transitions for nurse/admin use, routed
through the same state machine as automatic transitions.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import (
    AdminUser, PatientAccessProfile, PatientJourneyProfile, JourneyStageCode,
)
from app.api.deps_admin import get_current_admin
from app.infrastructure.db.repositories.hospital_scoped_repository import ensure_hospital_access
from app.services.patient_journey_state_machine import transition_stage, InvalidStageTransitionError
from app.schemas.patient_journey_admin import JourneyStageTransitionRequest, JourneyStageResponse

router = APIRouter(prefix="/admin", tags=["admin_patient_journey"])


@router.post("/patients/{patient_access_profile_id}/journey-stage", response_model=JourneyStageResponse)
async def transition_patient_stage(
    patient_access_profile_id: uuid.UUID,
    payload: JourneyStageTransitionRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    profile = db.query(PatientAccessProfile).filter(PatientAccessProfile.id == patient_access_profile_id).first()
    if not profile:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "بیمار پیدا نشد.")

    hospital_id = profile.qr_access_point.hospital_id

    ensure_hospital_access(admin, db, hospital_id)

    journey = (
        db.query(PatientJourneyProfile)
        .filter(
            PatientJourneyProfile.patient_access_profile_id == patient_access_profile_id,
            PatientJourneyProfile.is_active.is_(True),
        )
        .order_by(PatientJourneyProfile.created_at.desc())
        .first()
    )
    if not journey:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "مسیر درمانی فعالی برای این بیمار پیدا نشد.")

    try:
        target = JourneyStageCode(payload.target_stage)
    except ValueError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "کد مرحله نامعتبر است.")

    try:
        journey = transition_stage(db, journey, target, hospital_id=hospital_id, triggered_by="manual")
    except InvalidStageTransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))

    return JourneyStageResponse(current_stage=journey.current_stage.value)