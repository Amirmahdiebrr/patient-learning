"""
app/api/v1/admin_followup.py

Read-only view of scheduled follow-up tasks, hospital-scoped.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import FollowUpTask, AdminUser
from app.schemas.followup_admin import FollowUpTaskResponse
from app.api.deps_admin import get_current_admin
from app.infrastructure.db.repositories.hospital_scoped_repository import ensure_hospital_access

router = APIRouter(prefix="/admin", tags=["admin_followup"])


@router.get("/followup-tasks", response_model=list[FollowUpTaskResponse])
async def list_followup_tasks(
    hospital_id: uuid.UUID,
    status_filter: str | None = None,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    ensure_hospital_access(admin, db, hospital_id)

    query = db.query(FollowUpTask).filter(FollowUpTask.hospital_id == hospital_id)
    if status_filter:
        query = query.filter(FollowUpTask.status == status_filter)

    return query.order_by(FollowUpTask.scheduled_at.desc()).limit(200).all()