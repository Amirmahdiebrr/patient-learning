# app/api/v1/admin_auth.py
"""
app/api/v1/admin_auth.py

Admin login/logout, plus hospital self-service signup. On success,
the JWT is set as an httpOnly cookie (never returned in the JSON body
or stored in localStorage/JS-reachable storage) plus a separate,
JS-unreadable CSRF cookie the admin pages embed into a <meta> tag -
see admin_panel.py.

register-hospital lets a hospital create its own Hospital row + an
AdminUser scoped to it as HOSPITAL_ADMIN, without a super_admin having
to onboard them manually via /admin/admin-users.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.csrf import issue_csrf_cookie
from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import AdminUser, Hospital, Role, RoleCode, AdminRoleAssignment
from app.schemas.admin import HospitalSignupRequest, slugify
from app.core.security import verify_password, hash_password, create_admin_access_token
from app.services.rate_limit_service import check_rate_limit

router = APIRouter(prefix="/admin/auth", tags=["admin_auth"])

LOGIN_IP_LIMIT = 15
LOGIN_IP_WINDOW_SECONDS = 900
LOGIN_EMAIL_LIMIT = 5
LOGIN_EMAIL_WINDOW_SECONDS = 900

SIGNUP_IP_LIMIT = 10
SIGNUP_IP_WINDOW_SECONDS = 3600


class AdminLoginRequest(BaseModel):
    email: str
    password: str


class AdminLoginResponse(BaseModel):
    full_name: str
    email: str


def _set_admin_session_cookies(response: Response, admin: AdminUser) -> None:
    token = create_admin_access_token(str(admin.id))
    response.set_cookie(
        key=settings.ADMIN_TOKEN_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        max_age=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    issue_csrf_cookie(response, settings.ADMIN_CSRF_COOKIE_NAME)


@router.post("/login", response_model=AdminLoginResponse)
async def admin_login(
    payload: AdminLoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
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

    _set_admin_session_cookies(response, admin)

    return AdminLoginResponse(full_name=admin.full_name, email=admin.email)


@router.post("/register-hospital", response_model=AdminLoginResponse)
async def register_hospital(
    payload: HospitalSignupRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    client_ip = request.client.host if request.client else "unknown"

    ip_result = check_rate_limit(f"hospital_signup_ip:{client_ip}", SIGNUP_IP_LIMIT, SIGNUP_IP_WINDOW_SECONDS)
    if not ip_result.allowed:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="تعداد درخواست‌های ثبت‌نام از این IP بیش از حد مجاز است.",
            headers={"Retry-After": str(ip_result.retry_after_seconds)},
        )

    existing = db.query(AdminUser).filter(AdminUser.email == payload.admin_email.lower()).first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "این ایمیل قبلاً ثبت شده است.")

    role = db.query(Role).filter(Role.code == RoleCode.HOSPITAL_ADMIN).first()
    if not role:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "نقش‌ها هنوز seed نشده‌اند.")

    hospital = Hospital(name=payload.hospital_name, slug=slugify(payload.hospital_name))
    db.add(hospital)
    db.flush()

    admin = AdminUser(
        email=payload.admin_email.lower(),
        password_hash=hash_password(payload.admin_password),
        full_name=payload.admin_full_name,
        is_active=True,
    )
    db.add(admin)
    db.flush()

    db.add(AdminRoleAssignment(admin_user_id=admin.id, role_id=role.id, hospital_id=hospital.id))
    db.commit()
    db.refresh(admin)

    _set_admin_session_cookies(response, admin)

    return AdminLoginResponse(full_name=admin.full_name, email=admin.email)


@router.post("/logout")
async def admin_logout(response: Response):
    response.delete_cookie(settings.ADMIN_TOKEN_COOKIE_NAME)
    response.delete_cookie(settings.ADMIN_CSRF_COOKIE_NAME)
    return {"ok": True}