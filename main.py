"""
main.py

Application entrypoint. Wires routers, static files, templates, and
the global exception handler that turns AccessGateError into the
"please scan the hospital QR code" landing page instead of a raw
401/403 response.
"""

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from app.core.logging_config import setup_logging, get_logger
from app.core.exceptions import AccessGateError
from app.core.templates import templates
from app.infrastructure.db.session import Base, engine

from app.api.v1.entry import router as entry_router
from app.api.v1.welcome import router as welcome_router
from app.api.v1.onboarding import router as onboarding_router
from app.api.v1.patient_home import router as patient_home_router
from app.api.v1.patient_lessons import router as patient_lessons_router
from app.api.v1.assistant import router as assistant_router
from app.api.v1.admin_auth import router as admin_auth_router
from app.api.v1.admin_users import router as admin_users_router
from app.api.v1.admin_hospitals import router as admin_hospitals_router
from app.api.v1.admin_qr import router as admin_qr_router
from app.api.v1.admin_content import router as admin_content_router
from app.api.v1.admin_panel import router as admin_panel_router

setup_logging()
logger = get_logger(__name__)

app = FastAPI(title="CuraLink Patient Education Platform", version="0.1.0")

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(entry_router)
app.include_router(welcome_router)
app.include_router(onboarding_router)
app.include_router(patient_home_router)
app.include_router(patient_lessons_router)
app.include_router(assistant_router)
app.include_router(admin_auth_router)
app.include_router(admin_users_router)
app.include_router(admin_hospitals_router)
app.include_router(admin_qr_router)
app.include_router(admin_content_router)
app.include_router(admin_panel_router)


@app.exception_handler(AccessGateError)
async def access_gate_exception_handler(request: Request, exc: AccessGateError):
    logger.info(f"[AccessGate] Blocked request to {request.url.path}: {exc.reason}")
    return templates.TemplateResponse(
        request, "scan_required.html", {"request": request}, status_code=403
    )


@app.get("/")
async def root_redirect_to_scan_notice(request: Request):
    """
    Direct navigation to the domain (no QR-derived cookie) always
    lands here, since every patient-facing route requires the access
    cookie and there is deliberately no other entry point.
    """
    return templates.TemplateResponse(request, "scan_required.html", {"request": request})


@app.on_event("startup")
async def on_startup():
    logger.info("CuraLink Patient Education Platform starting up.")
    # NOTE: Base.metadata.create_all() is intentionally NOT called here.
    # Schema changes must go through Alembic migrations once the DB is
    # provisioned - see alembic/ directory.


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)