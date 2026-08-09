"""
app/api/v1/admin_audit_log.py

Read-only audit log viewer. super_admin only - this shows who did
what across every hospital, which is platform-level oversight, not
something a hospital-scoped admin should see.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import AuditLog, AdminUser, RoleCode
from app.schemas.audit import AuditLogRowResponse, AuditLogResponse
from app.api.deps_admin import ScopeCheck

router = APIRouter(prefix="/admin", tags=["admin_audit_log"])

require_super_admin = ScopeCheck(allowed_roles=(RoleCode.SUPER_ADMIN,))


@router.get("/audit-log", response_model=AuditLogResponse)
async def get_audit_log(
    action: str | None = None,
    object_type: str | None = None,
    admin_id: uuid.UUID | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    admin: AdminUser = Depends(require_super_admin()),
    db: Session = Depends(get_db),
):
    query = db.query(AuditLog).options(joinedload(AuditLog.admin))

    if action:
        query = query.filter(AuditLog.action == action)
    if object_type:
        query = query.filter(AuditLog.object_type == object_type)
    if admin_id:
        query = query.filter(AuditLog.admin_id == admin_id)

    total = query.count()

    rows = (
        query.order_by(AuditLog.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return AuditLogResponse(
        total=total,
        rows=[
            AuditLogRowResponse(
                id=r.id,
                admin_id=r.admin_id,
                admin_email=r.admin.email if r.admin else None,
                action=r.action,
                object_type=r.object_type,
                object_id=r.object_id,
                before_values=r.before_values,
                after_values=r.after_values,
                ip_address=r.ip_address,
                created_at=r.created_at,
            )
            for r in rows
        ],
    )