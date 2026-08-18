"""
app/api/v1/nurse_auth.py

Self-service registration/login for nursing staff - independent from
the admin panel's auth (app/api/v1/admin_auth.py). A nurse registers
with her nursing-council license number and national ID under an
already-active hospital (and optionally one department), but stays
inactive until a hospital admin approves her - see
app/api/v1/admin_nurses.py. Login is by national_id (not email),
since national_id is the identifier nurses actually remember/carry.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.csrf import issue_csrf_cookie
from app.core.security import hash_password, verify_password, create_nurse_access_token
from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import NurseUser, Hospital, Department
from app.schemas.nurse import (
    NurseRegisterRequest, NurseRegisterResponse, NurseLoginRequest, NurseAuthResponse,
)
from app.services.rate_limit_service import check_rate_limit

router = APIRouter(prefix="/nurse/auth", tags=["nurse_auth"])

REGISTER_IP_LIMIT = 10
REGISTER_IP_WINDOW_SECONDS = 3600
LOGIN_IP_LIMIT = 15
LOGIN_IP_WINDOW_SECONDS = 900
LOGIN_NATIONAL_ID_LIMIT = 5
LOGIN_NATIONAL_ID_WINDOW_SECONDS = 900


def _set_nurse_session_cookies(response: Response, nurse: NurseUser) -> None:
    token = create_nurse_access_token(str(nurse.id))
    response.set_cookie(
        key=settings.NURSE_TOKEN_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        max_age=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    issue_csrf_cookie(response, settings.NURSE_CSRF_COOKIE_NAME)


@router.post("/register", response_model=NurseRegisterResponse)
async def nurse_register(
    payload: NurseRegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    client_ip = request.client.host if request.client else "unknown"
    ip_result = check_rate_limit(f"nurse_register_ip:{client_ip}", REGISTER_IP_LIMIT, REGISTER_IP_WINDOW_SECONDS)
    if not ip_result.allowed:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="تعداد درخواست‌های ثبت‌نام از این IP بیش از حد مجاز است.",
            headers={"Retry-After": str(ip_result.retry_after_seconds)},
        )

    hospital = db.query(Hospital).filter(Hospital.id == payload.hospital_id, Hospital.is_active.is_(True)).first()
    if not hospital:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "بیمارستان پیدا نشد یا هنوز تایید نشده است.")

    if payload.department_id:
        department = (
            db.query(Department)
            .filter(
                Department.id == payload.department_id,
                Department.hospital_id == payload.hospital_id,
                Department.is_active.is_(True),
            )
            .first()
        )
        if not department:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "بخش پیدا نشد یا به این بیمارستان تعلق ندارد.")

    existing_email = db.query(NurseUser).filter(NurseUser.email == payload.email.lower()).first()
    if existing_email:
        raise HTTPException(status.HTTP_409_CONFLICT, "این ایمیل قبلاً ثبت شده است.")

    existing_national_id = db.query(NurseUser).filter(NurseUser.national_id == payload.national_id).first()
    if existing_national_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "این کد ملی قبلاً ثبت شده است.")

    existing_license = (
        db.query(NurseUser)
        .filter(NurseUser.nursing_license_number == payload.nursing_license_number)
        .first()
    )
    if existing_license:
        raise HTTPException(status.HTTP_409_CONFLICT, "این کد نظام پرستاری قبلاً ثبت شده است.")

    nurse = NurseUser(
        hospital_id=payload.hospital_id,
        department_id=payload.department_id,
        full_name=payload.full_name,
        email=payload.email.lower(),
        national_id=payload.national_id,
        nursing_license_number=payload.nursing_license_number,
        password_hash=hash_password(payload.password),
        is_active=False,
    )
    db.add(nurse)
    db.commit()

    return NurseRegisterResponse()


@router.post("/login", response_model=NurseAuthResponse)
async def nurse_login(
    payload: NurseLoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    client_ip = request.client.host if request.client else "unknown"

    ip_result = check_rate_limit(f"nurse_login_ip:{client_ip}", LOGIN_IP_LIMIT, LOGIN_IP_WINDOW_SECONDS)
    if not ip_result.allowed:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="تعداد تلاش‌های ورود از این IP بیش از حد مجاز است.",
            headers={"Retry-After": str(ip_result.retry_after_seconds)},
        )

    national_id_result = check_rate_limit(
        f"nurse_login_national_id:{payload.national_id}", LOGIN_NATIONAL_ID_LIMIT, LOGIN_NATIONAL_ID_WINDOW_SECONDS
    )
    if not national_id_result.allowed:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="تعداد تلاش‌های ورود برای این حساب بیش از حد مجاز است.",
            headers={"Retry-After": str(national_id_result.retry_after_seconds)},
        )

    nurse = db.query(NurseUser).filter(NurseUser.national_id == payload.national_id).first()

    if not nurse or not verify_password(payload.password, nurse.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "کد ملی یا رمز عبور اشتباه است.")

    if not nurse.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "حساب شما هنوز توسط ادمین بیمارستان تایید نشده است.")

    _set_nurse_session_cookies(response, nurse)

    return NurseAuthResponse(full_name=nurse.full_name, email=nurse.email)


@router.post("/logout")
async def nurse_logout(response: Response):
    response.delete_cookie(settings.NURSE_TOKEN_COOKIE_NAME)
    response.delete_cookie(settings.NURSE_CSRF_COOKIE_NAME)
    return {"ok": True}