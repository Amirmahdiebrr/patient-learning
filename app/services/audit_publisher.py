"""
app/services/audit_publisher.py

Thin wrapper around event_bus.publish(AdminContentAction(...)) /
AdminAccessAction(...) so admin routes call one short function
instead of constructing the event dataclass inline every time. Purely
a naming/readability improvement - behavior is identical to
publishing the event directly.
"""

import uuid
from typing import Any

from app.core.event_bus import event_bus
from app.core.events import AdminContentAction, AdminAccessAction


def log_content_action(
    admin_id: uuid.UUID,
    action: str,
    object_type: str,
    object_id: uuid.UUID,
    ip_address: str | None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    event_bus.publish(AdminContentAction(
        admin_id=admin_id,
        action=action,
        object_type=object_type,
        object_id=object_id,
        before=before,
        after=after,
        ip_address=ip_address,
    ))


def log_access_action(
    admin_id: uuid.UUID,
    action: str,
    object_type: str,
    ip_address: str | None,
    object_id: uuid.UUID | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    event_bus.publish(AdminAccessAction(
        admin_id=admin_id,
        action=action,
        object_type=object_type,
        object_id=object_id,
        before=before,
        after=after,
        ip_address=ip_address,
    ))