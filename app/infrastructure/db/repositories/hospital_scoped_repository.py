"""
app/infrastructure/db/repositories/hospital_scoped_repository.py

Thin helper for hospital-scoped queries. Not a full repository
pattern (the project queries SQLAlchemy directly in routes, which is
an established, working pattern here) - just two reusable functions
that centralize "is this admin allowed to touch this hospital_id/
department_id", called from every admin route that touches
hospital- or department-owned data (admin_qr, admin_hospitals,
admin_patient_journey, admin_patient_report, admin_followup,
admin_analytics) instead of each one re-deriving the same
if-not-allowed-raise-403 check.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.infrastructure.db.models import AdminUser
from app.api.deps_admin import require_hospital_scope, require_department_scope


def ensure_hospital_access(admin: AdminUser, db: Session, hospital_id: uuid.UUID) -> None:
    if not require_hospital_scope(admin, db, hospital_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "دسترسی به این بیمارستان ندارید.")


def ensure_department_access(
    admin: AdminUser, db: Session, hospital_id: uuid.UUID, department_id: uuid.UUID
) -> None:
    if not require_department_scope(admin, db, hospital_id, department_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "دسترسی به این بخش ندارید.")