import uuid
from datetime import datetime

from pydantic import BaseModel


class FollowUpTaskResponse(BaseModel):
    id: uuid.UUID
    patient_access_profile_id: uuid.UUID
    hospital_id: uuid.UUID
    channel: str
    status: str
    scheduled_at: datetime
    sent_at: datetime | None
    provider_name: str | None
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}