"""
app/api/v1/referrals_public.py

Public-facing endpoint a hospital's HIS calls to submit a discharge
referral. Authenticated by X-API-Key (see deps_hospital_api_key.py),
not by admin JWT - this is meant to be called by another system, not
a logged-in staff member. Rate-limited per API key's hash to prevent
a misconfigured or malicious integration from flooding the platform.
"""

from fastapi import APIRouter, Depends, Request

from sqlalchemy.orm import Session

from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import PatientReferral, ReferralSource, ReferralStatus, HospitalApiKey
from app.schemas.referral import ReferralSubmitRequest, ReferralResponse
from app.api.deps_hospital_api_key import get_hospital_from_api_key
from app.api.deps_rate_limit import rate_limit
from app.core.encryption import hash_lookup_value
from app.services.referral_matching_service import try_match_patient
from app.core.event_bus import event_bus
from app.core.events import ReferralReceived

router = APIRouter(prefix="/api/v1", tags=["referrals_public"])

SUBMIT_RATE_LIMIT = 60
SUBMIT_RATE_WINDOW_SECONDS = 3600


@router.post("/referrals", response_model=ReferralResponse)
async def submit_referral(
    payload: ReferralSubmitRequest,
    request: Request,
    api_key: HospitalApiKey = Depends(get_hospital_from_api_key),
    db: Session = Depends(get_db),
    _rate_limit=Depends(rate_limit("referral_submit", SUBMIT_RATE_LIMIT, SUBMIT_RATE_WINDOW_SECONDS)),
):
    national_id_hash = hash_lookup_value(payload.national_id)
    matched_profile_id = try_match_patient(db, api_key.hospital_id, national_id_hash)

    referral = PatientReferral(
        hospital_id=api_key.hospital_id,
        patient_access_profile_id=matched_profile_id,
        source=ReferralSource.API,
        status=ReferralStatus.MATCHED if matched_profile_id else ReferralStatus.RECEIVED,
        api_key_id=api_key.id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        national_id=payload.national_id,
        national_id_hash=national_id_hash,
        phone_number=payload.phone_number,
        insurance_code=payload.insurance_code,
        chief_complaint=payload.chief_complaint,
        primary_diagnosis=payload.primary_diagnosis,
        secondary_diagnoses=payload.secondary_diagnoses,
        procedures_performed=payload.procedures_performed,
        medical_history=payload.medical_history,
        allergies=payload.allergies,
        vital_signs_summary=payload.vital_signs_summary,
        discharge_medications=payload.discharge_medications,
        care_instructions=payload.care_instructions,
        follow_up_recommendations=payload.follow_up_recommendations,
        additional_notes=payload.additional_notes,
        attending_physician_name=payload.attending_physician_name,
        referring_department_name=payload.referring_department_name,
        admission_date=payload.admission_date,
        discharge_date=payload.discharge_date,
        attachment_file_url=payload.attachment_file_url,
    )
    db.add(referral)
    db.commit()
    db.refresh(referral)

    event_bus.publish(ReferralReceived(
        referral_id=referral.id,
        hospital_id=api_key.hospital_id,
        source="api",
        matched=matched_profile_id is not None,
    ))

    return referral