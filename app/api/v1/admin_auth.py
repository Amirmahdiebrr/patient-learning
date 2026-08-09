"""
app/api/v1/admin_auth.py

Admin login. Patients have no login - this is exclusively for
hospital/department/content-manager staff and super admins.

Rate-limited on two independent keys to resist brute-force:
- by client IP (catches a single attacker hammering many accounts)
- by the submitted email (catches distributed attempts against one
  specific account)
Both checks happen before password verification so failed attempts
never touch bcrypt (which is intentionally slow) under load.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import AdminUser
from app.core.security import verify_password, create_admin_access_token
from app.services.rate_limit_service import check_rate_limit

router = APIRouter(prefix="/admin/auth", tags=["admin_auth"])

LOGIN_IP_LIMIT = 15
LOGIN_IP_WINDOW_SECONDS = 900
LOGIN_EMAIL_LIMIT = 5
LOGIN_EMAIL_WINDOW_SECONDS = 900


class AdminLoginRequest(BaseModel):
    email: str
    password: str


class AdminLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=AdminLoginResponse)
async def admin_login(payload: AdminLoginRequest, request: Request, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"

    ip_result = check_rate_limit(f"admin_login_ip:{client_ip}", LOGIN_IP_LIMIT, LOGIN_IP_WINDOW_SECONDS)
    if not ip_result.allowed:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="تعداد تلاش‌های ورود از این IP بیش از حد مجاز است. لطفاً کمی بعد دوباره تلاش کنید.",
            headers={"Retry-After": str(ip_result.retry_after_seconds)},
        )

    email_result = check_rate_limit(
        f"admin_login_email:{payload.email.lower()}", LOGIN_EMAIL_LIMIT, LOGIN_EMAIL_WINDOW_SECONDS
    )
    if not email_result.allowed:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="تعداد تلاش‌های ورود برای این حساب بیش از حد مجاز است. لطفاً کمی بعد دوباره تلاش کنید.",
            headers={"Retry-After": str(email_result.retry_after_seconds)},
        )

    admin = db.query(AdminUser).filter(AdminUser.email == payload.email.lower()).first()

    if not admin or not verify_password(payload.password, admin.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "ایمیل یا رمز عبور اشتباه است.")

    if not admin.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "این حساب غیرفعال است.")

    token = create_admin_access_token(str(admin.id))
    return AdminLoginResponse(access_token=token)