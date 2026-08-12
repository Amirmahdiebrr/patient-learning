"""
app/api/v1/admin_auth.py

Admin login/logout. On success, the JWT is set as an httpOnly cookie
(never returned in the JSON body or stored in localStorage/JS-reachable
storage) plus a separate, JS-unreadable CSRF cookie the admin pages
embed into a <meta> tag - see admin_panel.py.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.csrf import issue_csrf_cookie
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
    full_name: str
    email: str


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

    return AdminLoginResponse(full_name=admin.full_name, email=admin.email)


@router.post("/logout")
async def admin_logout(response: Response):
    response.delete_cookie(settings.ADMIN_TOKEN_COOKIE_NAME)
    response.delete_cookie(settings.ADMIN_CSRF_COOKIE_NAME)
    return {"ok": True}