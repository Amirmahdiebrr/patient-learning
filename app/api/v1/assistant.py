# app/api/v1/assistant.py
"""
app/api/v1/assistant.py

JSON endpoint for the patient AI assistant chat widget. Rate-limited
by IP to prevent a single browser/script from driving up AI provider
costs by spamming questions. Publishes AIConversationStarted when the
incoming request has no prior history (i.e. this is the first
question of a new conversation on the client).
"""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.event_bus import event_bus
from app.core.events import AIConversationStarted
from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import PatientJourneyProfile
from app.api.deps import AccessContext, get_access_context, get_active_journey
from app.api.deps_rate_limit import rate_limit
from app.schemas.patient import PatientAssistantAskRequest
from app.services.patient_assistant_service import PatientAssistantService
from app.infrastructure.external.ai_provider import AIProviderError
from app.core.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/assistant", tags=["assistant"])

assistant_service = PatientAssistantService()

ASK_RATE_LIMIT = 20
ASK_RATE_WINDOW_SECONDS = 3600


@router.post("/ask")
async def ask_assistant(
    payload: PatientAssistantAskRequest,
    journey: PatientJourneyProfile = Depends(get_active_journey),
    context: AccessContext = Depends(get_access_context),
    db: Session = Depends(get_db),
    _rate_limit=Depends(rate_limit("ai_chat", ASK_RATE_LIMIT, ASK_RATE_WINDOW_SECONDS)),
):
    if not journey.onboarding_completed_at:
        return JSONResponse({"error": "ابتدا باید پرسش‌نامه‌ی ورود را تکمیل کنید."}, status_code=400)

    if not payload.history:
        event_bus.publish(AIConversationStarted(
            patient_access_profile_id=context.patient_profile.id,
            question=payload.question,
        ))

    try:
        answer = await assistant_service.ask(
            db,
            journey,
            payload.question,
            payload.history,
            hospital_id=context.hospital_id,
            department_id=context.department_id,
            department_type_id=context.department.department_type_id,
        )
    except AIProviderError as exc:
        return JSONResponse({"error": str(exc)}, status_code=503)
    except Exception as exc:
        logger.error(f"[Assistant] Unexpected error: {exc}")
        return JSONResponse({"error": "پاسخ‌گویی با خطا مواجه شد. لطفاً دوباره تلاش کنید."}, status_code=500)

    return JSONResponse({"answer": answer})