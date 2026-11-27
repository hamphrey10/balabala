"""In-process typed event bus for decoupling packages."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from quant_deriv_ai.core.logging import get_logger

logger = get_logger(__name__)

EventHandler = Callable[["Event"], None]


@dataclass(frozen=True, slots=True)
class Event:
    """Immutable event envelope published on the bus."""

    topic: str
    payload: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class EventBus:
    """Synchronous publish/subscribe bus (async orchestration comes later)."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, topic: str, handler: EventHandler) -> None:
        if not topic:
            msg = "topic must be non-empty"
            raise ValueError(msg)
        self._subscribers[topic].append(handler)
        logger.debug(
            "event_bus.subscribe topic={} handlers={}",
            topic,
            len(self._subscribers[topic]),
        )

    def unsubscribe(self, topic: str, handler: EventHandler) -> None:
        handlers = self._subscribers.get(topic)
        if not handlers:
            return
        try:
            handlers.remove(handler)
        except ValueError:
            return

    def publish(self, event: Event) -> int:
        """Publish ``event`` to all handlers for its topic. Returns handler count invoked."""
        handlers = list(self._subscribers.get(event.topic, []))
        for handler in handlers:
            handler(event)
        logger.debug(
            "event_bus.publish topic={} event_id={} handlers={}",
            event.topic,
            event.event_id,
            len(handlers),
        )
        return len(handlers)

    def topics(self) -> list[str]:
        return sorted(self._subscribers.keys())

    def clear(self) -> None:
        self._subscribers.clear()
