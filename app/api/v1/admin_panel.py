"""
app/api/v1/admin_panel.py

Renders the admin HTML shells. Auth is checked here server-side
(decoding the httpOnly cookie) so an unauthenticated visit redirects
straight to /admin/login instead of flashing the page and relying on
inconsistent client-side JS checks. Every page also gets csrf_token
in its context, since every admin page's inline script reads it from
a <meta name="csrf-token"> tag to send on state-changing requests -
forgetting this here means every POST/PATCH/DELETE from that page
fails CSRF verification with a 403.
"""

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from app.core.config import settings
from app.core.security import decode_admin_access_token
from app.core.templates import templates

router = APIRouter(prefix="/admin", tags=["admin_panel"])


def _is_authenticated(request: Request) -> bool:
    token = request.cookies.get(settings.ADMIN_TOKEN_COOKIE_NAME)
    return bool(token) and decode_admin_access_token(token) is not None


def _render_admin_page(request: Request, template_name: str, active_page: str):
    if not _is_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=303)

    return templates.TemplateResponse(
        request,
        template_name,
        {
            "request": request,
            "active_page": active_page,
            "csrf_token": request.cookies.get(settings.ADMIN_CSRF_COOKIE_NAME),
        },
    )


@router.get("/login")
async def admin_login_page(request: Request):
    return templates.TemplateResponse(request, "admin/login.html", {"request": request})


@router.get("/home")
async def admin_home_page(request: Request):
    return _render_admin_page(request, "admin/home.html", "home")


@router.get("/dashboard")
async def admin_dashboard_page(request: Request):
    return _render_admin_page(request, "admin/dashboard.html", "dashboard")


@router.get("/panel")
async def admin_panel_page(request: Request):
    return _render_admin_page(request, "admin/panel.html", "content")


@router.get("/patients")
async def admin_patients_report_page(request: Request):
    return _render_admin_page(request, "admin/patients.html", "patients")


@router.get("/referrals")
async def admin_referrals_page(request: Request):
    return _render_admin_page(request, "admin/referrals.html", "referrals")