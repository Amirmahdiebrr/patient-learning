"""
app/infrastructure/db/models/audit_log.py

Append-only audit trail. Rows are never updated or deleted by
application code - each row is a permanent record of "who did what,
when, from where, and what changed". Populated exclusively by event
handlers subscribed to AdminContentAction / AdminAccessAction (see
app/services/event_handlers/audit_handlers.py), never written to
directly by route handlers - this keeps the audit trail decoupled
from the business logic that triggers it.
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.infrastructure.db.session import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    admin_id = Column(UUID(as_uuid=True), ForeignKey("admin_users.id"), nullable=True, index=True)
    action = Column(String(50), nullable=False, index=True)
    object_type = Column(String(100), nullable=False, index=True)
    object_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    before_values = Column(JSONB, nullable=True)
    after_values = Column(JSONB, nullable=True)

    ip_address = Column(String(64), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    admin = relationship("AdminUser")