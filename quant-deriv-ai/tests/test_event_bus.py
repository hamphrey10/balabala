"""Tests for the internal event bus."""

from __future__ import annotations

from quant_deriv_ai.core.event_bus import Event, EventBus


def test_publish_subscribe() -> None:
    bus = EventBus()
    received: list[Event] = []

    def handler(event: Event) -> None:
        received.append(event)

    bus.subscribe("market.tick", handler)
    count = bus.publish(Event(topic="market.tick", payload={"symbol": "EURUSD"}))
    assert count == 1
    assert len(received) == 1
    assert received[0].payload["symbol"] == "EURUSD"


def test_unsubscribe() -> None:
    bus = EventBus()
    calls = {"n": 0}

    def handler(event: Event) -> None:
        calls["n"] += 1

    bus.subscribe("x", handler)
    bus.unsubscribe("x", handler)
    assert bus.publish(Event(topic="x")) == 0
    assert calls["n"] == 0


def test_topics_sorted() -> None:
    bus = EventBus()
    bus.subscribe("b", lambda e: None)
    bus.subscribe("a", lambda e: None)
    assert bus.topics() == ["a", "b"]
