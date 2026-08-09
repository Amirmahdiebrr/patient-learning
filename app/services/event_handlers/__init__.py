"""
app/services/event_handlers/__init__.py
"""

from app.services.event_handlers.logging_handlers import register_logging_handlers
from app.services.event_handlers.audit_handlers import register_audit_handlers
from app.services.event_handlers.followup_handlers import register_followup_handlers


def register_all_event_handlers() -> None:
    register_logging_handlers()
    register_audit_handlers()
    register_followup_handlers()