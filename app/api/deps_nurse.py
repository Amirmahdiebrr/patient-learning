"""
app/api/deps_nurse.py

Auth dependency for the nurse portal - fully separate from
deps_admin.py. Cookie-only (no Bearer fallback needed, nurses only
use the web UI), with the same CSRF double-submit pattern used
elsewhere for state-changing requests.
"""

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.csrf import verify_csrf
from app.core.security import decode_nurse_access_token
from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import NurseUser

_SAFE_METHODS = ("GET", "HEAD", "OPTIONS")


def get_current_nurse(
    request: Request,
    db: Session = Depends(get_db),
) -> NurseUser:
    token = request.cookies.get(settings.NURSE_TOKEN_COOKIE_NAME)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "لطفاً وارد حساب پرستاری شوید.")

    nurse_id = decode_nurse_access_token(token)
    if not nurse_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "نشست شما منقضی شده است.")

    nurse = db.query(NurseUser).filter(NurseUser.id == nurse_id, NurseUser.is_active.is_(True)).first()
    if not nurse:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "حساب پرستاری پیدا نشد یا غیرفعال است.")

    if request.method not in _SAFE_METHODS:
        submitted = request.headers.get(settings.CSRF_HEADER_NAME)
        verify_csrf(request, settings.NURSE_CSRF_COOKIE_NAME, submitted)

    return nurse