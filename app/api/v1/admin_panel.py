"""
app/api/v1/admin_panel.py
"""

from fastapi import APIRouter, Request

from app.core.templates import templates

router = APIRouter(prefix="/admin", tags=["admin_panel"])


@router.get("/login")
async def admin_login_page(request: Request):
    return templates.TemplateResponse(request, "admin/login.html", {"request": request})


@router.get("/home")
async def admin_home_page(request: Request):
    return templates.TemplateResponse(request, "admin/home.html", {"request": request, "active_page": "home"})


@router.get("/dashboard")
async def admin_dashboard_page(request: Request):
    return templates.TemplateResponse(request, "admin/dashboard.html", {"request": request, "active_page": "dashboard"})


@router.get("/panel")
async def admin_panel_page(request: Request):
    return templates.TemplateResponse(request, "admin/panel.html", {"request": request, "active_page": "content"})


@router.get("/patients")
async def admin_patients_report_page(request: Request):
    return templates.TemplateResponse(request, "admin/patients.html", {"request": request, "active_page": "patients"})