# app/api/v1/admin_ghost_browser.py
"""
app/api/v1/admin_ghost_browser.py

Super-admin-only "ghost mode": lets a platform super_admin enter the
EXACT same patient-facing experience (same templates, same lock/
timeline logic, same lessons/quizzes/assistant) as a real patient of
ANY hospital + department, with zero content restrictions - the ghost
session is a real PatientAccessProfile (flagged is_ghost=True) that
flows through the exact same routes (app/api/v1/patient_*.py) a real
patient uses, so nothing here is a separate "preview" renderer that
could ever drift from what patients actually see.
"""

import uuid

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_admin_access_token
from app.core.templates import templates
from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import AdminUser, RoleCode, AdminRoleAssignment, PatientJourneyProfile
from app.api.deps_admin import ScopeCheck
from app.schemas.ghost import (
    GhostSessionCreateRequest, GhostSessionEnterResponse,
    GhostSessionListResponse, GhostSessionRowResponse,
    GhostJumpStageRequest,
)
from app.services import ghost_session_service
from app.services.ghost_session_service import GhostSessionError

router = APIRouter(prefix="/admin", tags=["admin_ghost_browser"])

require_super_admin = ScopeCheck(allowed_roles=(RoleCode.SUPER_ADMIN,))


def _is_super_admin(db: Session, admin: AdminUser) -> bool:
    assignments = db.query(AdminRoleAssignment).filter(AdminRoleAssignment.admin_user_id == admin.id).all()
    return any(a.role.code == RoleCode.SUPER_ADMIN and a.hospital_id is None for a in assignments)


def _current_stage_of(db: Session, profile_id: uuid.UUID) -> str | None:
    journey = (
        db.query(PatientJourneyProfile)
        .filter(
            PatientJourneyProfile.patient_access_profile_id == profile_id,
            PatientJourneyProfile.is_active.is_(True),
        )
        .order_by(PatientJourneyProfile.created_at.desc())
        .first()
    )
    return journey.current_stage.value if journey else None


# ---------------- HTML page ----------------

@router.get("/ghost-browser")
async def ghost_browser_page(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get(settings.ADMIN_TOKEN_COOKIE_NAME)
    admin_id = decode_admin_access_token(token) if token else None
    if not admin_id:
        return RedirectResponse(url="/admin/login", status_code=303)

    admin = db.query(AdminUser).filter(AdminUser.id == admin_id, AdminUser.is_active.is_(True)).first()
    if not admin or not _is_super_admin(db, admin):
        return RedirectResponse(url="/admin/home", status_code=303)

    return templates.TemplateResponse(
        request,
        "admin/ghost_browser.html",
        {
            "request": request,
            "active_page": "ghost_browser",
            "csrf_token": request.cookies.get(settings.ADMIN_CSRF_COOKIE_NAME),
            "is_full_admin": True,
        },
    )


# ---------------- JSON API ----------------

@router.get("/ghost-sessions", response_model=GhostSessionListResponse)
async def list_ghost_sessions(
    admin: AdminUser = Depends(require_super_admin()),
    db: Session = Depends(get_db),
):
    profiles = ghost_session_service.list_ghost_sessions(db)
    rows = [
        GhostSessionRowResponse(
            id=p.id,
            ghost_label=p.ghost_label,
            hospital_name=p.hospital.name if p.hospital else "—",
            department_name=p.department.name if p.department else "—",
            current_stage=_current_stage_of(db, p.id),
            created_at=p.first_seen_at,
        )
        for p in profiles
    ]
    return GhostSessionListResponse(rows=rows)


@router.post("/ghost-sessions", response_model=GhostSessionEnterResponse)
async def create_ghost_session(
    payload: GhostSessionCreateRequest,
    response: Response,
    admin: AdminUser = Depends(require_super_admin()),
    db: Session = Depends(get_db),
):
    try:
        profile = ghost_session_service.create_ghost_session(
            db,
            admin_id=admin.id,
            hospital_id=payload.hospital_id,
            department_id=payload.department_id,
            ghost_label=payload.ghost_label,
            disease_id=payload.disease_id,
            treatment_id=payload.treatment_id,
            procedure_id=payload.procedure_id,
            has_surgery=payload.has_surgery,
            age=payload.age,
            gender=payload.gender,
            target_stage_code=payload.target_stage_code,
        )
    except GhostSessionError as exc:
        return JSONResponse({"detail": str(exc)}, status_code=422)

    ghost_session_service.enter_ghost_session_cookies(response, profile.id)
    return GhostSessionEnterResponse(redirect_url="/home")


@router.post("/ghost-sessions/{ghost_profile_id}/enter", response_model=GhostSessionEnterResponse)
async def enter_existing_ghost_session(
    ghost_profile_id: uuid.UUID,
    response: Response,
    admin: AdminUser = Depends(require_super_admin()),
    db: Session = Depends(get_db),
):
    try:
        profile = ghost_session_service.get_ghost_session_or_raise(db, ghost_profile_id)
    except GhostSessionError as exc:
        return JSONResponse({"detail": str(exc)}, status_code=404)

    ghost_session_service.enter_ghost_session_cookies(response, profile.id)
    return GhostSessionEnterResponse(redirect_url="/home")


@router.post("/ghost-sessions/{ghost_profile_id}/jump-stage")
async def jump_ghost_stage(
    ghost_profile_id: uuid.UUID,
    payload: GhostJumpStageRequest,
    admin: AdminUser = Depends(require_super_admin()),
    db: Session = Depends(get_db),
):
    try:
        journey = ghost_session_service.force_jump_stage(db, ghost_profile_id, payload.target_stage_code)
    except GhostSessionError as exc:
        return JSONResponse({"detail": str(exc)}, status_code=422)

    return JSONResponse({"current_stage": journey.current_stage.value})


@router.delete("/ghost-sessions/{ghost_profile_id}")
async def delete_ghost_session(
    ghost_profile_id: uuid.UUID,
    admin: AdminUser = Depends(require_super_admin()),
    db: Session = Depends(get_db),
):
    try:
        ghost_session_service.delete_ghost_session(db, ghost_profile_id)
    except GhostSessionError as exc:
        return JSONResponse({"detail": str(exc)}, status_code=404)
    return JSONResponse({"ok": True})


@router.get("/ghost-sessions/exit")
async def exit_ghost_session(
    admin: AdminUser = Depends(require_super_admin()),
):
    """
    Deliberately a plain GET, not a fetch/AJAX call - this is what
    lets it work as a simple <a href> link from inside the ghost-mode
    banner injected into patient pages by GhostBannerMiddleware. GET
    requests are exempt from the cookie-auth CSRF check
    (see deps_admin.py::_SAFE_METHODS), so no admin CSRF token needs
    to be threaded into a patient-facing page that has no admin
    <meta> tag to read it from.
    """
    response = RedirectResponse(url="/admin/ghost-browser", status_code=303)
    ghost_session_service.exit_ghost_session_cookies(response)
    return response