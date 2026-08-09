"""
app/infrastructure/db/models/followup.py

Post-discharge follow-up tasks. Created by an event handler on
PatientDischarged. No real SMS/call dispatch yet - see
app/services/followup/.
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Column, String, DateTime, ForeignKey, Enum, Text
from sqlalchemy.dialects.postgresql import UUID

from app.infrastructure.db.session import Base


class FollowUpChannel(str, PyEnum):
    SMS = "sms"
    CALL = "call"
    NOTIFICATION = "notification"


class FollowUpStatus(str, PyEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


class FollowUpTask(Base):
    __tablename__ = "followup_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    patient_access_profile_id = Column(UUID(as_uuid=True), ForeignKey("patient_access_profiles.id"), nullable=False, index=True)
    hospital_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=False, index=True)

    channel = Column(Enum(FollowUpChannel), nullable=False, default=FollowUpChannel.SMS)
    status = Column(Enum(FollowUpStatus), nullable=False, default=FollowUpStatus.PENDING, index=True)

    scheduled_at = Column(DateTime, nullable=False, index=True)
    sent_at = Column(DateTime, nullable=True)
    provider_name = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)