# app/api/v1/admin_auth.py
"""
app/api/v1/admin_auth.py
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
    hospital_pending_approval: bool = False


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

    pending = _has_pending_hospital(db, admin)

    return AdminLoginResponse(full_name=admin.full_name, email=admin.email, hospital_pending_approval=pending)


def _has_pending_hospital(db: Session, admin: AdminUser) -> bool:
    assignments = db.query(AdminRoleAssignment).filter(AdminRoleAssignment.admin_user_id == admin.id).all()
    if any(a.role.code == RoleCode.SUPER_ADMIN and a.hospital_id is None for a in assignments):
        return False
    hospital_ids = {a.hospital_id for a in assignments if a.hospital_id is not None}
    if not hospital_ids:
        return False
    active_count = db.query(Hospital).filter(Hospital.id.in_(hospital_ids), Hospital.is_active.is_(True)).count()
    return active_count == 0


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

    # بیمارستان تا تایید ادمین غیرفعال می‌ماند
    hospital = Hospital(
        name=payload.hospital_name,
        slug=slugify(payload.hospital_name),
        is_active=False,
        address=payload.hospital_address,
        phone_number=payload.hospital_phone,
        responsible_phone=payload.responsible_phone,
        responsible_national_id=payload.responsible_national_id,
    )
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

    return AdminLoginResponse(full_name=admin.full_name, email=admin.email, hospital_pending_approval=True)


@router.post("/logout")
async def admin_logout(response: Response):
    response.delete_cookie(settings.ADMIN_TOKEN_COOKIE_NAME)
    response.delete_cookie(settings.ADMIN_CSRF_COOKIE_NAME)
    return {"ok": True}