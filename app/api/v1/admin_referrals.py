"""
app/api/v1/admin_referrals.py

Admin-facing referral intake (manual entry), listing/review, and
hospital API key management for the HIS integration path.
"""

import hashlib
import secrets
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import (
    AdminUser, PatientReferral, ReferralSource, ReferralStatus, Hospital, HospitalApiKey,
)
from app.schemas.referral import (
    ReferralSubmitRequest, ReferralResponse, ReferralListResponse,
    HospitalApiKeyCreateRequest, HospitalApiKeyResponse, HospitalApiKeyCreatedResponse,
)
from app.api.deps_admin import get_current_admin, require_hospital_scope
from app.core.encryption import hash_lookup_value
from app.services.referral_matching_service import try_match_patient
from app.core.event_bus import event_bus
from app.core.events import ReferralReceived

router = APIRouter(prefix="/admin", tags=["admin_referrals"])


@router.post("/referrals", response_model=ReferralResponse)
async def create_manual_referral(
    hospital_id: uuid.UUID,
    payload: ReferralSubmitRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if not require_hospital_scope(admin, db, hospital_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "دسترسی به این بیمارستان ندارید.")

    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "بیمارستان پیدا نشد.")

    national_id_hash = hash_lookup_value(payload.national_id)
    matched_profile_id = try_match_patient(db, hospital_id, national_id_hash)

    referral = PatientReferral(
        hospital_id=hospital_id,
        patient_access_profile_id=matched_profile_id,
        source=ReferralSource.MANUAL,
        status=ReferralStatus.MATCHED if matched_profile_id else ReferralStatus.RECEIVED,
        created_by_admin_id=admin.id,
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
        hospital_id=hospital_id,
        source="manual",
        matched=matched_profile_id is not None,
    ))

    return referral


@router.get("/referrals", response_model=ReferralListResponse)
async def list_referrals(
    hospital_id: uuid.UUID,
    status_filter: str | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if not require_hospital_scope(admin, db, hospital_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "دسترسی به این بیمارستان ندارید.")

    query = db.query(PatientReferral).filter(PatientReferral.hospital_id == hospital_id)

    if status_filter:
        query = query.filter(PatientReferral.status == status_filter)

    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            (PatientReferral.first_name.ilike(term)) | (PatientReferral.last_name.ilike(term))
        )

    total = query.count()
    rows = query.order_by(PatientReferral.created_at.desc()).offset(offset).limit(min(limit, 200)).all()

    return ReferralListResponse(total=total, rows=rows)


@router.post("/referrals/{referral_id}/mark-reviewed", response_model=ReferralResponse)
async def mark_referral_reviewed(
    referral_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    referral = db.query(PatientReferral).filter(PatientReferral.id == referral_id).first()
    if not referral:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ارجاع پیدا نشد.")

    if not require_hospital_scope(admin, db, referral.hospital_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "دسترسی به این بیمارستان ندارید.")

    referral.status = ReferralStatus.REVIEWED
    db.commit()
    db.refresh(referral)
    return referral


# ==========================
# Hospital API keys (for HIS integration)
# ==========================

@router.post("/hospital-api-keys", response_model=HospitalApiKeyCreatedResponse)
async def create_hospital_api_key(
    payload: HospitalApiKeyCreateRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if not require_hospital_scope(admin, db, payload.hospital_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "دسترسی به این بیمارستان ندارید.")

    hospital = db.query(Hospital).filter(Hospital.id == payload.hospital_id).first()
    if not hospital:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "بیمارستان پیدا نشد.")

    raw_key = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    api_key = HospitalApiKey(
        hospital_id=payload.hospital_id,
        label=payload.label,
        key_hash=key_hash,
        created_by_admin_id=admin.id,
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)

    return HospitalApiKeyCreatedResponse(
        id=api_key.id, hospital_id=api_key.hospital_id, label=api_key.label,
        is_active=api_key.is_active, created_at=api_key.created_at, api_key=raw_key,
    )


@router.get("/hospitals/{hospital_id}/api-keys", response_model=list[HospitalApiKeyResponse])
async def list_hospital_api_keys(
    hospital_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if not require_hospital_scope(admin, db, hospital_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "دسترسی به این بیمارستان ندارید.")

    return (
        db.query(HospitalApiKey)
        .filter(HospitalApiKey.hospital_id == hospital_id)
        .order_by(HospitalApiKey.created_at.desc())
        .all()
    )


@router.post("/hospital-api-keys/{key_id}/revoke", response_model=HospitalApiKeyResponse)
async def revoke_hospital_api_key(
    key_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    api_key = db.query(HospitalApiKey).filter(HospitalApiKey.id == key_id).first()
    if not api_key:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "کلید پیدا نشد.")

    if not require_hospital_scope(admin, db, api_key.hospital_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "دسترسی به این بیمارستان ندارید.")

    api_key.is_active = False
    api_key.revoked_at = datetime.utcnow()
    db.commit()
    db.refresh(api_key)
    return api_key