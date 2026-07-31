"""
app/api/v1/admin_hospitals.py

Minimal admin CRUD for hospitals and departments - JSON API only for
now (a proper admin dashboard UI is a later phase; this unblocks
creating the hospital/department tree needed before any QR access
point can be issued). Departments can optionally link to a
StandardDepartmentType from the fixed taxonomy for consistent
classification across hospitals.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import Hospital, Department, RoleCode, StandardDepartmentType
from app.schemas.admin import (
    HospitalCreateRequest, HospitalResponse,
    DepartmentCreateRequest, DepartmentResponse,
    StandardDepartmentTypeResponse,
    slugify,
)
from app.api.deps_admin import ScopeCheck, require_hospital_scope, get_current_admin
from app.infrastructure.db.models import AdminUser

router = APIRouter(prefix="/admin", tags=["admin_hospitals"])

require_super_admin = ScopeCheck(allowed_roles=(RoleCode.SUPER_ADMIN,))


def _to_department_response(department: Department) -> DepartmentResponse:
    return DepartmentResponse(
        id=department.id,
        hospital_id=department.hospital_id,
        name=department.name,
        slug=department.slug,
        is_active=department.is_active,
        department_type_id=department.department_type_id,
        department_type_name=department.department_type.name if department.department_type else None,
    )


@router.post("/hospitals", response_model=HospitalResponse)
async def create_hospital(
    payload: HospitalCreateRequest,
    admin: AdminUser = Depends(require_super_admin()),
    db: Session = Depends(get_db),
):
    # Only super_admin creates hospitals - hospital/department admins
    # are scoped to hospitals that already exist.
    hospital = Hospital(name=payload.name, slug=slugify(payload.name))
    db.add(hospital)
    db.commit()
    db.refresh(hospital)
    return hospital


@router.get("/hospitals", response_model=list[HospitalResponse])
async def list_hospitals(
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return db.query(Hospital).filter(Hospital.is_active.is_(True)).order_by(Hospital.name).all()


@router.get("/department-types", response_model=list[StandardDepartmentTypeResponse])
async def list_department_types(
    macro_category: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(StandardDepartmentType)
    if macro_category:
        query = query.filter(StandardDepartmentType.macro_category == macro_category)
    types = query.order_by(StandardDepartmentType.macro_category, StandardDepartmentType.display_order).all()
    return [
        StandardDepartmentTypeResponse(
            id=t.id, macro_category=t.macro_category.value, code=t.code,
            name=t.name, display_order=t.display_order,
        )
        for t in types
    ]


@router.post("/departments", response_model=DepartmentResponse)
async def create_department(
    payload: DepartmentCreateRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if not require_hospital_scope(admin, db, payload.hospital_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "دسترسی به این بیمارستان ندارید.")

    hospital = db.query(Hospital).filter(Hospital.id == payload.hospital_id).first()
    if not hospital:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "بیمارستان پیدا نشد.")

    if payload.department_type_id:
        dept_type = db.query(StandardDepartmentType).filter(
            StandardDepartmentType.id == payload.department_type_id
        ).first()
        if not dept_type:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "نوع بخش استاندارد پیدا نشد.")

    department = Department(
        hospital_id=hospital.id,
        name=payload.name,
        slug=slugify(payload.name),
        department_type_id=payload.department_type_id,
    )
    db.add(department)
    db.commit()
    db.refresh(department)
    return _to_department_response(department)


@router.get("/hospitals/{hospital_id}/departments", response_model=list[DepartmentResponse])
async def list_departments(
    hospital_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    departments = (
        db.query(Department)
        .filter(Department.hospital_id == hospital_id, Department.is_active.is_(True))
        .order_by(Department.name)
        .all()
    )
    return [_to_department_response(d) for d in departments]