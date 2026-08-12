"""
app/api/deps_hospital_api_key.py

Authenticates a hospital's HIS integration via the X-API-Key header.
Only the SHA-256 hash of the key is ever stored, so a leaked database
does not expose usable keys.
"""

import hashlib

from fastapi import Header, HTTPException, status, Depends
from sqlalchemy.orm import Session

from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import HospitalApiKey


def _hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def get_hospital_from_api_key(
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> HospitalApiKey:
    key_hash = _hash_api_key(x_api_key)
    api_key = (
        db.query(HospitalApiKey)
        .filter(HospitalApiKey.key_hash == key_hash, HospitalApiKey.is_active.is_(True))
        .first()
    )
    if not api_key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "کلید API نامعتبر یا غیرفعال است.")
    return api_key