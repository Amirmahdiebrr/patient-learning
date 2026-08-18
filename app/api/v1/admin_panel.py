# app/api/v1/admin_panel.py
"""
app/api/v1/admin_panel.py
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_admin_access_token
from app.core.templates import templates
from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import AdminUser, Hospital, AdminRoleAssignment, RoleCode
from app.api.deps_admin import get_current_admin, is_full_admin

router = APIRouter(prefix="/admin", tags=["admin_panel"])


def _is_authenticated(request: Request) -> bool:
    token = request.cookies.get(settings.ADMIN_TOKEN_COOKIE_NAME)
    return bool(token) and decode_admin_access_token(token) is not None


def _has_pending_hospital(db: Session, admin: AdminUser) -> bool:
    assignments = db.query(AdminRoleAssignment).filter(AdminRoleAssignment.admin_user_id == admin.id).all()
    if any(a.role.code == RoleCode.SUPER_ADMIN and a.hospital_id is None for a in assignments):
        return False
    hospital_ids = {a.hospital_id for a in assignments if a.hospital_id is not None}
    if not hospital_ids:
        return False
    active_count = db.query(Hospital).filter(Hospital.id.in_(hospital_ids), Hospital.is_active.is_(True)).count()
    return active_count == 0


def _render_admin_page(
    request: Request, db: Session, template_name: str, active_page: str, require_full_admin: bool = False,
):
    token = request.cookies.get(settings.ADMIN_TOKEN_COOKIE_NAME)
    admin_id = decode_admin_access_token(token) if token else None
    if not admin_id:
        return RedirectResponse(url="/admin/login", status_code=303)

    admin = db.query(AdminUser).filter(AdminUser.id == admin_id, AdminUser.is_active.is_(True)).first()
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=303)

    full_admin = is_full_admin(admin, db)

    if not full_admin and _has_pending_hospital(db, admin):
        return templates.TemplateResponse(
            request, "admin/pending_approval.html", {"request": request},
        )

    if require_full_admin and not full_admin:
        return RedirectResponse(url="/admin/home", status_code=303)

    return templates.TemplateResponse(
        request,
        template_name,
        {
            "request": request,
            "active_page": active_page,
            "csrf_token": request.cookies.get(settings.ADMIN_CSRF_COOKIE_NAME),
            "is_full_admin": full_admin,
        },
    )


@router.get("/login")
async def admin_login_page(request: Request):
    return templates.TemplateResponse(request, "admin/login.html", {"request": request})


@router.get("/register-hospital")
async def admin_register_hospital_page(request: Request):
    return templates.TemplateResponse(request, "admin/register_hospital.html", {"request": request})


@router.get("/home")
async def admin_home_page(request: Request, db: Session = Depends(get_db)):
    return _render_admin_page(request, db, "admin/home.html", "home")


@router.get("/dashboard")
async def admin_dashboard_page(request: Request, db: Session = Depends(get_db)):
    return _render_admin_page(request, db, "admin/dashboard.html", "dashboard")


@router.get("/panel")
async def admin_panel_page(request: Request, db: Session = Depends(get_db)):
    return _render_admin_page(request, db, "admin/panel.html", "content", require_full_admin=True)


@router.get("/patients")
async def admin_patients_report_page(request: Request, db: Session = Depends(get_db)):
    return _render_admin_page(request, db, "admin/patients.html", "patients")


@router.get("/nurse-approvals")
async def admin_nurse_approvals_page(request: Request, db: Session = Depends(get_db)):
    return _render_admin_page(request, db, "admin/nurse_approvals.html", "nurse_approvals")


@router.get("/referrals")
async def admin_referrals_page(request: Request, db: Session = Depends(get_db)):
    return _render_admin_page(request, db, "admin/referrals.html", "referrals")


@router.get("/qr-codes")
async def admin_qr_codes_page(request: Request, db: Session = Depends(get_db)):
    return _render_admin_page(request, db, "admin/qr_codes.html", "qr_codes")


@router.get("/hospital-approvals")
async def admin_hospital_approvals_page(request: Request, db: Session = Depends(get_db)):
    return _render_admin_page(request, db, "admin/hospital_approvals.html", "hospital_approvals", require_full_admin=True)