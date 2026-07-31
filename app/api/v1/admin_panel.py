"""
app/api/v1/admin_panel.py

Server-rendered admin pages: a login form and a single-page content
builder. These pages only render HTML shells - all real work happens
client-side via fetch() calls to the existing JSON admin API, using a
JWT stored in the browser's localStorage (added as a Bearer header by
the page's own JS). No server-side auth check on these two GET routes
themselves; the JSON API underneath still enforces auth on every
write/read of admin data.
"""

from fastapi import APIRouter, Request

from app.core.templates import templates

router = APIRouter(prefix="/admin", tags=["admin_panel"])


@router.get("/login")
async def admin_login_page(request: Request):
    return templates.TemplateResponse(request, "admin/login.html", {"request": request})


@router.get("/panel")
async def admin_panel_page(request: Request):
    return templates.TemplateResponse(request, "admin/panel.html", {"request": request})