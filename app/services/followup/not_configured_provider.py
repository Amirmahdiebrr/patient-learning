"""
app/services/followup/not_configured_provider.py

Default provider until a real SMS/call/notification vendor is
integrated. Always fails cleanly, never raises.
"""

from app.infrastructure.db.models import FollowUpTask
from app.services.followup.base_provider import BaseFollowUpProvider
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class NotConfiguredProvider(BaseFollowUpProvider):
    name = "not_configured"

    def send(self, task: FollowUpTask) -> bool:
        logger.warning(
            f"[FollowUp] No provider configured for channel '{task.channel.value}' - task {task.id} left pending."
        )
        return False