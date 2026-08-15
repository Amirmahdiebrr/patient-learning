"""
app/api/v1/admin_hospitals.py
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.event_bus import event_bus
from app.core.events import AdminContentAction
from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import (
    Hospital, Department, RoleCode, StandardDepartmentType, AdminUser, AdminRoleAssignment,
)
from app.schemas.admin import (
    HospitalCreateRequest, HospitalUpdateRequest, HospitalResponse,
    DepartmentCreateRequest, DepartmentUpdateRequest, DepartmentResponse,
    StandardDepartmentTypeResponse, PendingHospitalResponse,
    slugify,
)
from app.api.deps_admin import ScopeCheck, get_current_admin
from app.api.deps_common import client_ip
from app.infrastructure.db.repositories.hospital_scoped_repository import ensure_hospital_access

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


def _hospital_snapshot(hospital: Hospital) -> dict:
    return {"name": hospital.name, "is_active": hospital.is_active}


def _department_snapshot(department: Department) -> dict:
    return {
        "name": department.name,
        "department_type_id": str(department.department_type_id) if department.department_type_id else None,
        "is_active": department.is_active,
    }


# ==========================
# Hospital
# ==========================

@router.post("/hospitals", response_model=HospitalResponse)
async def create_hospital(
    payload: HospitalCreateRequest,
    request: Request,
    admin: AdminUser = Depends(require_super_admin()),
    db: Session = Depends(get_db),
):
    hospital = Hospital(name=payload.name, slug=slugify(payload.name))
    db.add(hospital)
    db.commit()
    db.refresh(hospital)

    event_bus.publish(AdminContentAction(
        admin_id=admin.id,
        action="create",
        object_type="hospital",
        object_id=hospital.id,
        before=None,
        after=_hospital_snapshot(hospital),
        ip_address=client_ip(request),
    ))

    return hospital


@router.get("/hospitals", response_model=list[HospitalResponse])
async def list_hospitals(
    search: str | None = None,
    include_inactive: bool = False,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(Hospital)
    if not include_inactive:
        query = query.filter(Hospital.is_active.is_(True))
    if search:
        query = query.filter(Hospital.name.ilike(f"%{search}%"))
    return query.order_by(Hospital.name).all()


@router.get("/hospitals/pending-approval", response_model=list[PendingHospitalResponse])
async def list_pending_hospitals(
    admin: AdminUser = Depends(require_super_admin()),
    db: Session = Depends(get_db),
):
    hospitals = (
        db.query(Hospital)
        .filter(Hospital.is_active.is_(False))
        .order_by(Hospital.created_at.desc())
        .all()
    )

    results = []
    for h in hospitals:
        assignments = db.query(AdminRoleAssignment).filter(AdminRoleAssignment.hospital_id == h.id).all()
        assignment = next((a for a in assignments if a.role.code == RoleCode.HOSPITAL_ADMIN), None)
        responsible = assignment.admin_user if assignment else None

        results.append(PendingHospitalResponse(
            id=h.id,
            name=h.name,
            address=h.address,
            phone_number=h.phone_number,
            responsible_phone=h.responsible_phone,
            responsible_national_id=h.responsible_national_id,
            responsible_full_name=responsible.full_name if responsible else None,
            responsible_email=responsible.email if responsible else None,
            created_at=h.created_at,
        ))

    return results


@router.get("/my-hospitals", response_model=list[HospitalResponse])
async def list_my_hospitals(
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    assignments = (
        db.query(AdminRoleAssignment)
        .filter(AdminRoleAssignment.admin_user_id == admin.id)
        .all()
    )

    is_global_super_admin = any(
        a.role.code == RoleCode.SUPER_ADMIN and a.hospital_id is None for a in assignments
    )
    if is_global_super_admin:
        return db.query(Hospital).filter(Hospital.is_active.is_(True)).order_by(Hospital.name).all()

    hospital_ids = {a.hospital_id for a in assignments if a.hospital_id is not None}
    if not hospital_ids:
        return []

    return (
        db.query(Hospital)
        .filter(Hospital.id.in_(hospital_ids), Hospital.is_active.is_(True))
        .order_by(Hospital.name)
        .all()
    )


@router.patch("/hospitals/{hospital_id}", response_model=HospitalResponse)
async def update_hospital(
    hospital_id: uuid.UUID,
    payload: HospitalUpdateRequest,
    request: Request,
    admin: AdminUser = Depends(require_super_admin()),
    db: Session = Depends(get_db),
):
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "بیمارستان پیدا نشد.")

    before = _hospital_snapshot(hospital)

    hospital.name = payload.name
    hospital.slug = slugify(payload.name)
    db.commit()
    db.refresh(hospital)

    event_bus.publish(AdminContentAction(
        admin_id=admin.id,
        action="update",
        object_type="hospital",
        object_id=hospital.id,
        before=before,
        after=_hospital_snapshot(hospital),
        ip_address=client_ip(request),
    ))

    return hospital


@router.post("/hospitals/{hospital_id}/deactivate", response_model=HospitalResponse)
async def deactivate_hospital(
    hospital_id: uuid.UUID,
    request: Request,
    admin: AdminUser = Depends(require_super_admin()),
    db: Session = Depends(get_db),
):
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "بیمارستان پیدا نشد.")

    before = _hospital_snapshot(hospital)
    hospital.is_active = False
    db.commit()
    db.refresh(hospital)

    event_bus.publish(AdminContentAction(
        admin_id=admin.id,
        action="deactivate",
        object_type="hospital",
        object_id=hospital.id,
        before=before,
        after=_hospital_snapshot(hospital),
        ip_address=client_ip(request),
    ))

    return hospital


@router.post("/hospitals/{hospital_id}/reactivate", response_model=HospitalResponse)
async def reactivate_hospital(
    hospital_id: uuid.UUID,
    request: Request,
    admin: AdminUser = Depends(require_super_admin()),
    db: Session = Depends(get_db),
):
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "بیمارستان پیدا نشد.")

    before = _hospital_snapshot(hospital)
    hospital.is_active = True
    db.commit()
    db.refresh(hospital)

    event_bus.publish(AdminContentAction(
        admin_id=admin.id,
        action="reactivate",
        object_type="hospital",
        object_id=hospital.id,
        before=before,
        after=_hospital_snapshot(hospital),
        ip_address=client_ip(request),
    ))

    return hospital


# ==========================
# StandardDepartmentType
# ==========================

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


# ==========================
# Department
# ==========================

@router.post("/departments", response_model=DepartmentResponse)
async def create_department(
    payload: DepartmentCreateRequest,
    request: Request,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    ensure_hospital_access(admin, db, payload.hospital_id)

    hospital = db.query(Hospital).filter(Hospital.id == payload.hospital_id).first()
    if not hospital:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "بیمارستان پیدا نشد.")

    dept_type = db.query(StandardDepartmentType).filter(
        StandardDepartmentType.id == payload.department_type_id
    ).first()
    if not dept_type:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "نوع بخش استاندارد پیدا نشد.")

    name = (payload.name or "").strip() or dept_type.name

    department = Department(
        hospital_id=hospital.id,
        name=name,
        slug=slugify(name),
        department_type_id=dept_type.id,
    )
    db.add(department)
    db.commit()
    db.refresh(department)

    event_bus.publish(AdminContentAction(
        admin_id=admin.id,
        action="create",
        object_type="department",
        object_id=department.id,
        before=None,
        after=_department_snapshot(department),
        ip_address=client_ip(request),
    ))

    return _to_department_response(department)


@router.get("/hospitals/{hospital_id}/departments", response_model=list[DepartmentResponse])
async def list_departments(
    hospital_id: uuid.UUID,
    search: str | None = None,
    include_inactive: bool = False,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(Department).filter(Department.hospital_id == hospital_id)
    if not include_inactive:
        query = query.filter(Department.is_active.is_(True))
    if search:
        query = query.filter(Department.name.ilike(f"%{search}%"))
    departments = query.order_by(Department.name).all()
    return [_to_department_response(d) for d in departments]


@router.patch("/departments/{department_id}", response_model=DepartmentResponse)
async def update_department(
    department_id: uuid.UUID,
    payload: DepartmentUpdateRequest,
    request: Request,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "بخش پیدا نشد.")

    ensure_hospital_access(admin, db, department.hospital_id)

    if payload.department_type_id:
        dept_type = db.query(StandardDepartmentType).filter(
            StandardDepartmentType.id == payload.department_type_id
        ).first()
        if not dept_type:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "نوع بخش استاندارد پیدا نشد.")

    before = _department_snapshot(department)

    department.name = payload.name
    department.slug = slugify(payload.name)
    department.department_type_id = payload.department_type_id
    db.commit()
    db.refresh(department)

    event_bus.publish(AdminContentAction(
        admin_id=admin.id,
        action="update",
        object_type="department",
        object_id=department.id,
        before=before,
        after=_department_snapshot(department),
        ip_address=client_ip(request),
    ))

    return _to_department_response(department)


@router.post("/departments/{department_id}/deactivate", response_model=DepartmentResponse)
async def deactivate_department(
    department_id: uuid.UUID,
    request: Request,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "بخش پیدا نشد.")

    ensure_hospital_access(admin, db, department.hospital_id)

    before = _department_snapshot(department)
    department.is_active = False
    db.commit()
    db.refresh(department)

    event_bus.publish(AdminContentAction(
        admin_id=admin.id,
        action="deactivate",
        object_type="department",
        object_id=department.id,
        before=before,
        after=_department_snapshot(department),
        ip_address=client_ip(request),
    ))

    return _to_department_response(department)


@router.post("/departments/{department_id}/reactivate", response_model=DepartmentResponse)
async def reactivate_department(
    department_id: uuid.UUID,
    request: Request,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "بخش پیدا نشد.")

    ensure_hospital_access(admin, db, department.hospital_id)

    before = _department_snapshot(department)
    department.is_active = True
    db.commit()
    db.refresh(department)

    event_bus.publish(AdminContentAction(
        admin_id=admin.id,
        action="reactivate",
        object_type="department",
        object_id=department.id,
        before=before,
        after=_department_snapshot(department),
        ip_address=client_ip(request),
    ))

    return _to_department_response(department)