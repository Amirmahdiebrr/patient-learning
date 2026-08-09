"""
app/api/v1/admin_users.py

super_admin-only endpoints to create new admin users and assign them
roles scoped to a hospital/department. This is the piece that lets a
super_admin onboard hospital_admin/department_admin/doctor/
content_manager accounts without touching the DB directly.

Publishes AdminAccessAction for admin-user create/deactivate and
role-assignment create/delete - these govern WHO can access WHAT,
which is a different (and more sensitive) audit surface than content
edits.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.event_bus import event_bus
from app.core.events import AdminAccessAction
from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import (
    AdminUser, AdminRoleAssignment, Role, RoleCode, Hospital, Department,
)
from app.schemas.admin import (
    AdminUserCreateRequest, AdminUserResponse,
    RoleAssignmentCreateRequest, RoleAssignmentResponse,
)
from app.api.deps_admin import ScopeCheck
from app.core.security import hash_password

router = APIRouter(prefix="/admin", tags=["admin_users"])

require_super_admin = ScopeCheck(allowed_roles=(RoleCode.SUPER_ADMIN,))


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _to_assignment_response(a: AdminRoleAssignment) -> RoleAssignmentResponse:
    return RoleAssignmentResponse(
        id=a.id,
        admin_user_id=a.admin_user_id,
        role_code=a.role.code.value,
        hospital_id=a.hospital_id,
        department_id=a.department_id,
        created_at=a.created_at,
    )


@router.post("/admin-users", response_model=AdminUserResponse)
async def create_admin_user(
    payload: AdminUserCreateRequest,
    request: Request,
    admin: AdminUser = Depends(require_super_admin()),
    db: Session = Depends(get_db),
):
    existing = db.query(AdminUser).filter(AdminUser.email == payload.email.lower()).first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "این ایمیل قبلاً ثبت شده است.")

    new_admin = AdminUser(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        is_active=True,
    )
    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)

    event_bus.publish(AdminAccessAction(
        admin_id=admin.id,
        action="create_admin",
        object_type="admin_user",
        object_id=new_admin.id,
        before=None,
        after={"email": new_admin.email, "full_name": new_admin.full_name},
        ip_address=_client_ip(request),
    ))

    return new_admin


@router.get("/admin-users", response_model=list[AdminUserResponse])
async def list_admin_users(
    admin: AdminUser = Depends(require_super_admin()),
    db: Session = Depends(get_db),
):
    return db.query(AdminUser).order_by(AdminUser.created_at.desc()).all()


@router.post("/admin-users/{admin_user_id}/deactivate", response_model=AdminUserResponse)
async def deactivate_admin_user(
    admin_user_id: uuid.UUID,
    request: Request,
    admin: AdminUser = Depends(require_super_admin()),
    db: Session = Depends(get_db),
):
    target = db.query(AdminUser).filter(AdminUser.id == admin_user_id).first()
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ادمین پیدا نشد.")

    target.is_active = False
    db.commit()
    db.refresh(target)

    event_bus.publish(AdminAccessAction(
        admin_id=admin.id,
        action="deactivate_admin",
        object_type="admin_user",
        object_id=target.id,
        before={"is_active": True},
        after={"is_active": False},
        ip_address=_client_ip(request),
    ))

    return target


@router.post("/role-assignments", response_model=RoleAssignmentResponse)
async def create_role_assignment(
    payload: RoleAssignmentCreateRequest,
    request: Request,
    admin: AdminUser = Depends(require_super_admin()),
    db: Session = Depends(get_db),
):
    target_admin = db.query(AdminUser).filter(AdminUser.id == payload.admin_user_id).first()
    if not target_admin:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ادمین پیدا نشد.")

    role = db.query(Role).filter(Role.code == RoleCode(payload.role_code)).first()
    if not role:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "نقش پیدا نشد - اول seed_lookup_data را اجرا کن.")

    scoped_roles = {RoleCode.HOSPITAL_ADMIN, RoleCode.DEPARTMENT_ADMIN, RoleCode.DOCTOR}
    if role.code in scoped_roles and not payload.hospital_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "این نقش نیاز به hospital_id دارد.")

    if payload.hospital_id:
        hospital = db.query(Hospital).filter(Hospital.id == payload.hospital_id).first()
        if not hospital:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "بیمارستان پیدا نشد.")

    if payload.department_id:
        department = (
            db.query(Department)
            .filter(Department.id == payload.department_id, Department.hospital_id == payload.hospital_id)
            .first()
        )
        if not department:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "بخش پیدا نشد یا به این بیمارستان تعلق ندارد.")

    existing = (
        db.query(AdminRoleAssignment)
        .filter(
            AdminRoleAssignment.admin_user_id == payload.admin_user_id,
            AdminRoleAssignment.role_id == role.id,
            AdminRoleAssignment.hospital_id == payload.hospital_id,
            AdminRoleAssignment.department_id == payload.department_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "این نقش قبلاً به این ادمین اختصاص داده شده است.")

    assignment = AdminRoleAssignment(
        admin_user_id=payload.admin_user_id,
        role_id=role.id,
        hospital_id=payload.hospital_id,
        department_id=payload.department_id,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)

    event_bus.publish(AdminAccessAction(
        admin_id=admin.id,
        action="assign_role",
        object_type="role_assignment",
        object_id=assignment.id,
        before=None,
        after={
            "admin_user_id": str(payload.admin_user_id),
            "role_code": payload.role_code,
            "hospital_id": str(payload.hospital_id) if payload.hospital_id else None,
            "department_id": str(payload.department_id) if payload.department_id else None,
        },
        ip_address=_client_ip(request),
    ))

    return _to_assignment_response(assignment)


@router.get("/admin-users/{admin_user_id}/role-assignments", response_model=list[RoleAssignmentResponse])
async def list_role_assignments(
    admin_user_id: uuid.UUID,
    admin: AdminUser = Depends(require_super_admin()),
    db: Session = Depends(get_db),
):
    assignments = (
        db.query(AdminRoleAssignment)
        .filter(AdminRoleAssignment.admin_user_id == admin_user_id)
        .all()
    )
    return [_to_assignment_response(a) for a in assignments]


@router.delete("/role-assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role_assignment(
    assignment_id: uuid.UUID,
    request: Request,
    admin: AdminUser = Depends(require_super_admin()),
    db: Session = Depends(get_db),
):
    assignment = db.query(AdminRoleAssignment).filter(AdminRoleAssignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "این نقش پیدا نشد.")

    snapshot = {
        "admin_user_id": str(assignment.admin_user_id),
        "role_code": assignment.role.code.value,
        "hospital_id": str(assignment.hospital_id) if assignment.hospital_id else None,
        "department_id": str(assignment.department_id) if assignment.department_id else None,
    }
    assignment_id_copy = assignment.id

    db.delete(assignment)
    db.commit()

    event_bus.publish(AdminAccessAction(
        admin_id=admin.id,
        action="revoke_role",
        object_type="role_assignment",
        object_id=assignment_id_copy,
        before=snapshot,
        after=None,
        ip_address=_client_ip(request),
    ))