"""
app/api/deps_admin.py

Admin authentication (JWT bearer) + RBAC scope-checking dependencies.
Also populates the per-request logging context (admin_id) as soon as
the token is verified, so every log line emitted for the rest of this
request automatically carries that context.

require_hospital_scope and the new require_department_scope are the
tenant-isolation guardrails: every admin route that touches a
specific hospital's or department's data MUST call one of these
before reading/writing it. Content endpoints (diseases, lessons,
sections, media, quizzes) deliberately do NOT check hospital scope -
that content is a shared library by design (see
EducationSection.department_type_id), not owned by any one hospital.
"""

import uuid
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.security import decode_admin_access_token
from app.core.request_context import admin_id_var
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

    admin_id_var.set(str(admin.id))

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
    True if this admin may act anywhere within the given hospital:
    they're a global super_admin, OR they hold a hospital_admin /
    department_admin / content_manager assignment scoped to this
    exact hospital_id (regardless of which department that assignment
    is further scoped to, if any).

    Use this for hospital-level actions (creating a department,
    editing the hospital itself). For actions scoped to one specific
    department, use require_department_scope instead - a
    department_admin assigned to Department A should NOT pass this
    check's more permissive sibling and act on Department B just
    because both are in the same hospital.
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


def require_department_scope(admin: AdminUser, db: Session, hospital_id: uuid.UUID, department_id: uuid.UUID) -> bool:
    """
    Stricter than require_hospital_scope: True only if this admin may
    act on this SPECIFIC department. Passes for:
    - a global super_admin
    - a hospital_admin/content_manager scoped to this hospital with
      no department restriction (department_id IS NULL on their
      assignment - they cover the whole hospital)
    - a department_admin/doctor whose assignment's department_id
      matches exactly

    This is what prevents a department_admin for "Orthopedics" from
    creating/managing QR access points (or anything else scoped to a
    single department) under "Cardiology" in the same hospital, which
    require_hospital_scope alone would incorrectly allow.
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

        if a.role.code in (RoleCode.DEPARTMENT_ADMIN, RoleCode.DOCTOR) and a.department_id == department_id:
            return True

    return False