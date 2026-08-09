"""
app/schemas/audit.py

Pydantic v2 DTOs for the admin-facing audit log viewer.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuditLogRowResponse(BaseModel):
    id: uuid.UUID
    admin_id: uuid.UUID | None
    admin_email: str | None
    action: str
    object_type: str
    object_id: uuid.UUID | None
    before_values: dict[str, Any] | None
    after_values: dict[str, Any] | None
    ip_address: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogResponse(BaseModel):
    total: int
    rows: list[AuditLogRowResponse]