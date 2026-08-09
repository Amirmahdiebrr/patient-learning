"""
app/core/event_bus.py

Minimal in-process, synchronous publish/subscribe event bus.

Deliberately NOT a message broker (Kafka/RabbitMQ/Redis Streams) -
at CuraLink's current scale, an in-process bus is enough and avoids
operational overhead. If cross-process delivery is ever needed (e.g.
a separate worker for SMS follow-ups), this is the seam where a
Redis-backed or broker-backed implementation could replace this one
without touching any caller.

Contract: a handler exception is logged and swallowed, never
re-raised. Domain events are side effects of a successful action
(e.g. "a lesson was completed") - a broken analytics or audit handler
must never break the patient-facing request that triggered it.
"""

from collections import defaultdict
from typing import Callable

from app.core.logging_config import get_logger

logger = get_logger(__name__)


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[type, list[Callable]] = defaultdict(list)

    def subscribe(self, event_type: type, handler: Callable) -> None:
        self._subscribers[event_type].append(handler)

    def publish(self, event: object) -> None:
        event_type = type(event)
        handlers = self._subscribers.get(event_type, [])

        for handler in handlers:
            try:
                handler(event)
            except Exception as exc:
                logger.error(
                    f"[EventBus] handler '{getattr(handler, '__name__', handler)}' "
                    f"failed for event '{event_type.__name__}': {exc!r}"
                )


# Single shared instance for the whole app - simple singleton, no DI
# container needed at this scale.
event_bus = EventBus()