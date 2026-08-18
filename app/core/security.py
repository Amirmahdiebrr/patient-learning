"""
app/core/security.py

Password hashing + JWT issuing/verification.
Patients never use this - they only use the QR access-gate cookies
(see access_gate_service.py). Admin and Nurse each get their own
token functions so the two portals stay fully independent, even
though they share the same underlying JWT secret/algorithm.
"""

from datetime import datetime, timedelta

from jose import jwt, JWTError
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(raw_password: str) -> str:
    return pwd_context.hash(raw_password)


def verify_password(raw_password: str, password_hash: str) -> bool:
    try:
        return pwd_context.verify(raw_password, password_hash)
    except Exception:
        return False


def create_admin_access_token(admin_user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": admin_user_id, "typ": "admin", "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_admin_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("typ") != "admin":
            return None
        return payload.get("sub")
    except JWTError:
        return None


def create_nurse_access_token(nurse_user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": nurse_user_id, "typ": "nurse", "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_nurse_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("typ") != "nurse":
            return None
        return payload.get("sub")
    except JWTError:
        return None