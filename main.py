# main.py
"""
main.py
"""

import os

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.logging_config import setup_logging, get_logger
from app.core.exceptions import AccessGateError
from app.core.templates import templates
from app.services.event_handlers import register_all_event_handlers
from app.api.middleware.logging_middleware import RequestLoggingMiddleware
from app.api.middleware.security_headers_middleware import SecurityHeadersMiddleware
from app.api.middleware.ghost_banner_middleware import GhostBannerMiddleware

from app.api.v1.entry import router as entry_router
from app.api.v1.welcome import router as welcome_router
from app.api.v1.onboarding import router as onboarding_router
from app.api.v1.patient_home import router as patient_home_router
from app.api.v1.patient_journey_page import router as patient_journey_page_router
from app.api.v1.patient_lessons import router as patient_lessons_router
from app.api.v1.patient_self_auth import router as patient_self_auth_router
from app.api.v1.patient_profile import router as patient_profile_router
from app.api.v1.patient_procedures import router as patient_procedures_router
from app.api.v1.assistant import router as assistant_router
from app.api.v1.admin_auth import router as admin_auth_router
from app.api.v1.admin_users import router as admin_users_router
from app.api.v1.admin_hospitals import router as admin_hospitals_router
from app.api.v1.admin_qr import router as admin_qr_router
from app.api.v1.admin_content import router as admin_content_router
from app.api.v1.admin_smart_import import router as admin_smart_import_router
from app.api.v1.admin_procedure_import import router as admin_procedure_import_router
from app.api.v1.admin_lesson_draft import router as admin_lesson_draft_router
from app.api.v1.admin_media_upload import router as admin_media_upload_router
from app.api.v1.admin_patient_report import router as admin_patient_report_router
from app.api.v1.admin_audit_log import router as admin_audit_log_router
from app.api.v1.admin_patient_journey import router as admin_patient_journey_router
from app.api.v1.admin_followup import router as admin_followup_router
from app.api.v1.admin_analytics import router as admin_analytics_router
from app.api.v1.admin_referrals import router as admin_referrals_router
from app.api.v1.admin_nurses import router as admin_nurses_router
from app.api.v1.admin_ghost_browser import router as admin_ghost_browser_router
from app.api.v1.referrals_public import router as referrals_public_router
from app.api.v1.admin_panel import router as admin_panel_router
from app.api.v1.nurse_auth import router as nurse_auth_router
from app.api.v1.nurse_dashboard import router as nurse_dashboard_router

setup_logging()
logger = get_logger(__name__)

app = FastAPI(title="CuraLink Patient Education Platform", version="0.1.0")

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(GhostBannerMiddleware)

os.makedirs(settings.MEDIA_UPLOAD_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

ALL_ROUTERS = [
    entry_router, welcome_router, onboarding_router, patient_home_router, patient_journey_page_router,
    patient_lessons_router, patient_self_auth_router, patient_profile_router, patient_procedures_router,
    assistant_router,
    admin_auth_router, admin_users_router,
    admin_hospitals_router, admin_qr_router, admin_content_router, admin_smart_import_router,
    admin_procedure_import_router,
    admin_lesson_draft_router,
    admin_media_upload_router, admin_patient_report_router, admin_audit_log_router,
    admin_patient_journey_router, admin_followup_router, admin_analytics_router,
    admin_referrals_router, admin_nurses_router, admin_ghost_browser_router,
    referrals_public_router, admin_panel_router,
    nurse_auth_router, nurse_dashboard_router,
]

for router in ALL_ROUTERS:
    app.include_router(router)


@app.exception_handler(AccessGateError)
async def access_gate_exception_handler(request: Request, exc: AccessGateError):
    logger.info(f"[AccessGate] Blocked request to {request.url.path}: {exc.reason}")
    return templates.TemplateResponse(request, "scan_required.html", {"request": request}, status_code=403)


@app.get("/")
async def home_page(request: Request):
    return templates.TemplateResponse(request, "home.html", {"request": request})


@app.on_event("startup")
async def on_startup():
    logger.info("CuraLink Patient Education Platform starting up.")
    register_all_event_handlers()
    logger.info("[EventBus] Domain event handlers registered.")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)