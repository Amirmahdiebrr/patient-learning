"""
app/services/access_gate_service.py

Core logic for the QR-only access gate:
- generating the opaque secret embedded in a printed QR code
- resolving that secret to an active QRAccessPoint
- signing/verifying the two cookies that prove "this browser scanned
  a valid QR" (access cookie) and "this browser already has an
  anonymous patient profile" (profile cookie)

Cookies are signed with itsdangerous (not JWT) because they carry no
claims that need standard verification tooling - just tamper-proofing
of a UUID, which itsdangerous does with far less overhead than JWT.
"""

import secrets
import uuid
from datetime import datetime

from itsdangerous import URLSafeTimedSerializer, BadSignature
from sqlalchemy.orm import Session

from app.core.config import settings
from app.infrastructure.db.models import QRAccessPoint, QRAccessPointStatus, PatientAccessProfile

ACCESS_COOKIE_SALT = "curalink-access-cookie"
PROFILE_COOKIE_SALT = "curalink-profile-cookie"

_serializer = URLSafeTimedSerializer(settings.ACCESS_COOKIE_SECRET)


def generate_qr_token() -> str:
    """
    Generates the opaque, unguessable secret that gets embedded in a
    printed QR code's URL (?token=...). Only called by the admin panel
    when creating a new QRAccessPoint.
    """
    return secrets.token_urlsafe(settings.ACCESS_TOKEN_BYTES)


def resolve_active_qr_access_point(db: Session, token: str) -> QRAccessPoint | None:
    if not token:
        return None

    access_point = (
        db.query(QRAccessPoint)
        .filter(
            QRAccessPoint.access_token == token,
            QRAccessPoint.status == QRAccessPointStatus.ACTIVE,
        )
        .first()
    )
    return access_point


def sign_access_cookie(qr_access_point_id: uuid.UUID) -> str:
    return _serializer.dumps(str(qr_access_point_id), salt=ACCESS_COOKIE_SALT)


def verify_access_cookie(cookie_value: str | None) -> uuid.UUID | None:
    if not cookie_value:
        return None
    try:
        raw = _serializer.loads(cookie_value, salt=ACCESS_COOKIE_SALT, max_age=None)
        return uuid.UUID(raw)
    except (BadSignature, ValueError):
        return None


def sign_profile_cookie(patient_access_profile_id: uuid.UUID) -> str:
    return _serializer.dumps(str(patient_access_profile_id), salt=PROFILE_COOKIE_SALT)


def verify_profile_cookie(cookie_value: str | None) -> uuid.UUID | None:
    if not cookie_value:
        return None
    try:
        raw = _serializer.loads(cookie_value, salt=PROFILE_COOKIE_SALT, max_age=None)
        return uuid.UUID(raw)
    except (BadSignature, ValueError):
        return None


def get_or_create_patient_profile(
    db: Session,
    qr_access_point_id: uuid.UUID,
    existing_profile_id: uuid.UUID | None,
) -> PatientAccessProfile:
    """
    If the browser already carries a valid, existing profile cookie,
    reuse that profile (and bump last_seen_at). Otherwise create a
    brand-new anonymous profile bound to this access point.
    """
    profile = None

    if existing_profile_id:
        profile = (
            db.query(PatientAccessProfile)
            .filter(PatientAccessProfile.id == existing_profile_id)
            .first()
        )

    if profile:
        profile.last_seen_at = datetime.utcnow()
        db.commit()
        db.refresh(profile)
        return profile

    profile = PatientAccessProfile(qr_access_point_id=qr_access_point_id)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile