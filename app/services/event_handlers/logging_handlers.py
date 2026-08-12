"""
app/services/event_handlers/logging_handlers.py
"""

from app.core.event_bus import event_bus
from app.core.events import (
    QRScanned,
    PatientRegistered,
    PatientStageChanged,
    PatientDischarged,
    LessonCompleted,
    QuizCompleted,
    AIConversationStarted,
    ReferralReceived,
)
from app.core.logging_config import get_logger

logger = get_logger(__name__)

_LOGGED_EVENT_TYPES = (
    QRScanned,
    PatientRegistered,
    PatientStageChanged,
    PatientDischarged,
    LessonCompleted,
    QuizCompleted,
    AIConversationStarted,
    ReferralReceived,
)


def _log_event(event: object) -> None:
    logger.info(f"[Event] {type(event).__name__}: {event}")


def register_logging_handlers() -> None:
    for event_type in _LOGGED_EVENT_TYPES:
        event_bus.subscribe(event_type, _log_event)