"""
app/services/followup/followup_scheduler.py

Creates FollowUpTask rows for a future dispatcher. Does not send
anything itself.
"""

import uuid
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.infrastructure.db.models import FollowUpTask, FollowUpChannel, FollowUpStatus
from app.core.logging_config import get_logger

logger = get_logger(__name__)


def schedule_followup(
    db: Session,
    patient_access_profile_id: uuid.UUID,
    hospital_id: uuid.UUID,
    channel: FollowUpChannel = FollowUpChannel.SMS,
    delay_days: int = 3,
) -> FollowUpTask:
    task = FollowUpTask(
        patient_access_profile_id=patient_access_profile_id,
        hospital_id=hospital_id,
        channel=channel,
        status=FollowUpStatus.PENDING,
        scheduled_at=datetime.utcnow() + timedelta(days=delay_days),
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    logger.info(f"[FollowUp] scheduled {channel.value} follow-up for {patient_access_profile_id} at {task.scheduled_at}")

    return task