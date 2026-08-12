"""
app/api/deps_admin.py

Admin authentication + RBAC scope-checking dependencies.

Auth now prefers an httpOnly cookie (set by /admin/auth/login) over
the old "JWT sitting in localStorage" approach, which was readable by
any JS running on the page (including an XSS in patient-authored
lesson content). A Bearer header is still accepted as a fallback for
non-browser API clients.

Cookie-based sessions are vulnerable to CSRF (the browser attaches
the cookie automatically on cross-site requests) in a way Bearer
headers are not, so state-changing requests authenticated via cookie
additionally require a matching X-CSRF-Token header - see
app/core/csrf.py.
"""

import uuid
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.csrf import verify_csrf
from app.core.security import decode_admin_access_token
from app.core.request_context import admin_id_var
from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import AdminUser, AdminRoleAssignment, RoleCode

bearer_scheme = HTTPBearer(auto_error=False)

_SAFE_METHODS = ("GET", "HEAD", "OPTIONS")


def get_current_admin(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> AdminUser:
    used_cookie = False
    token = None

    if credentials is not None:
        token = credentials.credentials
    else:
        token = request.cookies.get(settings.ADMIN_TOKEN_COOKIE_NAME)
        used_cookie = token is not None

    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "توکن احراز هویت ارسال نشده است.")

    admin_id = decode_admin_access_token(token)
    if not admin_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "توکن نامعتبر یا منقضی‌شده است.")

    admin = db.query(AdminUser).filter(AdminUser.id == admin_id, AdminUser.is_active.is_(True)).first()
    if not admin:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "حساب ادمین پیدا نشد یا غیرفعال است.")

    if used_cookie and request.method not in _SAFE_METHODS:
        submitted = request.headers.get(settings.CSRF_HEADER_NAME)
        verify_csrf(request, settings.ADMIN_CSRF_COOKIE_NAME, submitted)

    admin_id_var.set(str(admin.id))

    return admin


@dataclass
class ScopeCheck:
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
    True if the admin can act on hospital-scoped resources for this
    hospital. Includes DOCTOR now - a doctor's assignment always
    carries a hospital_id (see admin_users.py's scoped_roles set), and
    clinical staff legitimately need to see hospital-scoped read data
    (patient report, dashboard, followups) even if they're not a
    hospital_admin/content_manager.
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
            RoleCode.HOSPITAL_ADMIN, RoleCode.DEPARTMENT_ADMIN,
            RoleCode.CONTENT_MANAGER, RoleCode.DOCTOR,
        ):
            return True

    return False


def require_department_scope(admin: AdminUser, db: Session, hospital_id: uuid.UUID, department_id: uuid.UUID) -> bool:
    """
    True if the admin can act on this specific department. A DOCTOR
    (or DEPARTMENT_ADMIN) assignment with department_id=None means
    "this whole hospital" (a hospital-wide doctor, not tied to one
    department) - previously only an exact department_id match was
    accepted, which silently locked out any doctor assigned without a
    specific department.
    """
    assignments = (
        db.query(AdminRoleAssignment)
        .filter(AdminRoleAssignment.admin_user_id == admin.id)
        .all()
    )

    for a in assignments:
        if a.role.code == RoleCode.SUPER_ADMIN and a.hospital_id is None:
            return True

        if a.hospital_id != hospital_id:
            continue

        if a.role.code in (RoleCode.HOSPITAL_ADMIN, RoleCode.CONTENT_MANAGER) and a.department_id is None:
            return True

        if a.role.code in (RoleCode.DEPARTMENT_ADMIN, RoleCode.DOCTOR) and (
            a.department_id == department_id or a.department_id is None
        ):
            return True

    return False