"""
app/services/followup/provider_registry.py

Maps a FollowUpChannel to its provider. Replace individual entries
once a real vendor is chosen - no other file changes.
"""

from app.infrastructure.db.models import FollowUpChannel
from app.services.followup.base_provider import BaseFollowUpProvider
from app.services.followup.not_configured_provider import NotConfiguredProvider

_PROVIDERS: dict[FollowUpChannel, BaseFollowUpProvider] = {
    FollowUpChannel.SMS: NotConfiguredProvider(),
    FollowUpChannel.CALL: NotConfiguredProvider(),
    FollowUpChannel.NOTIFICATION: NotConfiguredProvider(),
}


def get_provider_for_channel(channel: FollowUpChannel) -> BaseFollowUpProvider:
    return _PROVIDERS[channel]