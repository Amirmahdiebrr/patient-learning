"""
app/services/followup/base_provider.py

Abstract follow-up delivery provider. No real vendor wired yet.
"""

from abc import ABC, abstractmethod

from app.infrastructure.db.models import FollowUpTask


class BaseFollowUpProvider(ABC):
    name: str = "base"

    @abstractmethod
    def send(self, task: FollowUpTask) -> bool:
        ...