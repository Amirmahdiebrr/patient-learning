"""
app/services/event_handlers/audit_handlers.py

Subscribes to AdminContentAction / AdminAccessAction and persists
each one as a permanent AuditLog row. Uses its own short-lived DB
session (not the request's session) because event handlers must
never assume the publishing request's session is still open or in a
usable state when the handler runs.
"""

from dataclasses import asdict

from app.core.event_bus import event_bus
from app.core.events import AdminContentAction, AdminAccessAction
from app.core.logging_config import get_logger
from app.infrastructure.db.session import SessionLocal
from app.infrastructure.db.models import AuditLog

logger = get_logger(__name__)


def _persist_audit_event(event: AdminContentAction | AdminAccessAction) -> None:
    db = SessionLocal()
    try:
        db.add(AuditLog(
            admin_id=event.admin_id,
            action=event.action,
            object_type=event.object_type,
            object_id=event.object_id,
            before_values=event.before,
            after_values=event.after,
            ip_address=event.ip_address,
            created_at=event.occurred_at,
        ))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def register_audit_handlers() -> None:
    event_bus.subscribe(AdminContentAction, _persist_audit_event)
    event_bus.subscribe(AdminAccessAction, _persist_audit_event)