"""
app/api/deps_admin.py

Admin authentication (JWT bearer) + RBAC scope-checking dependencies.
"""

import uuid
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.security import decode_admin_access_token
from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import AdminUser, AdminRoleAssignment, RoleCode

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> AdminUser:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "توکن احراز هویت ارسال نشده است.")

    admin_id = decode_admin_access_token(credentials.credentials)
    if not admin_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "توکن نامعتبر یا منقضی‌شده است.")

    admin = db.query(AdminUser).filter(AdminUser.id == admin_id, AdminUser.is_active.is_(True)).first()
    if not admin:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "حساب ادمین پیدا نشد یا غیرفعال است.")

    return admin


@dataclass
class ScopeCheck:
    """
    Callable FastAPI dependency factory: require_scope(hospital_id=...)
    returns a dependency that raises 403 unless the current admin has
    an assignment covering that scope (or is a global super_admin).
    """
    allowed_roles: tuple[RoleCode, ...] | None = None

    def __call__(self):
        def _check(
            admin: AdminUser = Depends(get_current_admin),
            db: Session = Depends(get_db),
        ) -> AdminUser:
            assignments = (
                db.query(AdminRoleAssignment)
                .filter(AdminRoleAssignment.admin_user_id == admin.id)
                .all()
            )

            is_super_admin = any(
                a.role.code == RoleCode.SUPER_ADMIN and a.hospital_id is None
                for a in assignments
            )

            if is_super_admin:
                return admin

            if self.allowed_roles:
                has_role = any(a.role.code in self.allowed_roles for a in assignments)
                if not has_role:
                    raise HTTPException(status.HTTP_403_FORBIDDEN, "دسترسی کافی برای این عملیات ندارید.")

            return admin

        return _check


def require_hospital_scope(admin: AdminUser, db: Session, hospital_id: uuid.UUID) -> bool:
    """
    Explicit scope check used inside a route body when the resource's
    hospital_id is only known after parsing the request (e.g. creating
    a QR access point under a specific hospital/department).
    """
    assignments = (
        db.query(AdminRoleAssignment)
        .filter(AdminRoleAssignment.admin_user_id == admin.id)
        .all()
    )

    for a in assignments:
        if a.role.code == RoleCode.SUPER_ADMIN and a.hospital_id is None:
            return True
        if a.hospital_id == hospital_id and a.role.code in (
            RoleCode.HOSPITAL_ADMIN, RoleCode.DEPARTMENT_ADMIN, RoleCode.CONTENT_MANAGER,
        ):
            return True

    return False