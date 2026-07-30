"""
app/api/v1/admin_auth.py

Admin login. Patients have no login - this is exclusively for
hospital/department/content-manager staff and super admins.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import AdminUser
from app.core.security import verify_password, create_admin_access_token

router = APIRouter(prefix="/admin/auth", tags=["admin_auth"])

class AdminLoginRequest(BaseModel):
    email: str
    password: str


class AdminLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=AdminLoginResponse)
async def admin_login(payload: AdminLoginRequest, db: Session = Depends(get_db)):
    admin = db.query(AdminUser).filter(AdminUser.email == payload.email.lower()).first()

    if not admin or not verify_password(payload.password, admin.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "ایمیل یا رمز عبور اشتباه است.")

    if not admin.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "این حساب غیرفعال است.")

    token = create_admin_access_token(str(admin.id))
    return AdminLoginResponse(access_token=token)