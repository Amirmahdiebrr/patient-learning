"""
app/services/referral_matching_service.py

Attempts to auto-link an incoming referral to an existing
PatientAccessProfile by exact-matching national_id_hash against
PatientRegistration rows for the same hospital. Never decrypts
anything - the hash comparison is enough.
"""

import uuid

from sqlalchemy.orm import Session

from app.infrastructure.db.models import PatientRegistration, PatientAccessProfile, QRAccessPoint


def try_match_patient(db: Session, hospital_id: uuid.UUID, national_id_hash: str | None) -> uuid.UUID | None:
    if not national_id_hash:
        return None

    registration = (
        db.query(PatientRegistration)
        .join(PatientAccessProfile, PatientRegistration.patient_access_profile_id == PatientAccessProfile.id)
        .join(QRAccessPoint, PatientAccessProfile.qr_access_point_id == QRAccessPoint.id)
        .filter(
            PatientRegistration.national_id_hash == national_id_hash,
            QRAccessPoint.hospital_id == hospital_id,
        )
        .order_by(PatientRegistration.created_at.desc())
        .first()
    )
    return registration.patient_access_profile_id if registration else None