"""
app/services/followup/dispatcher.py

Stub for a future cron/worker that picks up due FollowUpTask rows.
Not wired to any scheduler yet - safe to call manually.
"""

from datetime import datetime

from sqlalchemy.orm import Session

from app.infrastructure.db.models import FollowUpTask, FollowUpStatus
from app.services.followup.provider_registry import get_provider_for_channel


def run_due_followups(db: Session) -> int:
    due_tasks = (
        db.query(FollowUpTask)
        .filter(FollowUpTask.status == FollowUpStatus.PENDING, FollowUpTask.scheduled_at <= datetime.utcnow())
        .all()
    )

    processed = 0
    for task in due_tasks:
        provider = get_provider_for_channel(task.channel)
        success = provider.send(task)

        task.status = FollowUpStatus.SENT if success else FollowUpStatus.FAILED
        task.sent_at = datetime.utcnow() if success else None
        task.provider_name = provider.name
        if not success:
            task.error_message = "Provider not configured or send failed."

        processed += 1

    db.commit()
    return processed