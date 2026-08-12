"""
app/api/v1/admin_analytics.py

Read-only analytics endpoints, hospital-scoped.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import AdminUser
from app.api.deps_admin import get_current_admin
from app.infrastructure.db.repositories.hospital_scoped_repository import ensure_hospital_access
from app.schemas.analytics import DashboardSummaryResponse
from app.services import analytics_service

router = APIRouter(prefix="/admin", tags=["admin_analytics"])


@router.get("/analytics/dashboard-summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    hospital_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    ensure_hospital_access(admin, db, hospital_id)

    return analytics_service.get_hospital_dashboard_summary(db, hospital_id)