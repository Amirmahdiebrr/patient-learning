"""
app/api/v1/admin_analytics.py

Read-only analytics endpoints, hospital-scoped.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import AdminUser
from app.api.deps_admin import get_current_admin, require_hospital_scope
from app.schemas.analytics import DashboardSummaryResponse
from app.services import analytics_service

router = APIRouter(prefix="/admin", tags=["admin_analytics"])


@router.get("/analytics/dashboard-summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    hospital_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if not require_hospital_scope(admin, db, hospital_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "دسترسی به این بیمارستان ندارید.")

    return analytics_service.get_hospital_dashboard_summary(db, hospital_id)
