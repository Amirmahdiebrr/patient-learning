"""
app/api/v1/assistant.py

JSON endpoint for the patient AI assistant chat widget.
"""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import PatientJourneyProfile
from app.api.deps import get_access_context, get_active_journey
from app.schemas.patient import PatientAssistantAskRequest
from app.services.patient_assistant_service import PatientAssistantService
from app.infrastructure.external.ai_provider import AIProviderError
from app.core.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/assistant", tags=["assistant"])

assistant_service = PatientAssistantService()


@router.post("/ask")
async def ask_assistant(
    payload: PatientAssistantAskRequest,
    journey: PatientJourneyProfile = Depends(get_active_journey),
    _context=Depends(get_access_context),
    db: Session = Depends(get_db),
):
    if not journey.onboarding_completed_at:
        return JSONResponse({"error": "ابتدا باید پرسش‌نامه‌ی ورود را تکمیل کنید."}, status_code=400)

    try:
        answer = await assistant_service.ask(db, journey, payload.question, payload.history)
    except AIProviderError as exc:
        return JSONResponse({"error": str(exc)}, status_code=503)
    except Exception as exc:
        logger.error(f"[Assistant] Unexpected error: {exc}")
        return JSONResponse({"error": "پاسخ‌گویی با خطا مواجه شد. لطفاً دوباره تلاش کنید."}, status_code=500)

    return JSONResponse({"answer": answer})