"""Unit tests for ThresholdDetector.

Covers:
- Fires event when threshold reached within window
- Does NOT fire when below threshold
- Resets counter after window expires
- Tracks multiple IPs independently
- Threshold of 1 fires immediately
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from src.core.detector import ThresholdDetector
from src.core.events import EventBroker, SecurityEvent


def _utc(minutes_ago: int = 0) -> datetime:
    """Deterministic timestamp helper."""
    base = datetime(2026, 4, 4, 12, 0, 0, tzinfo=timezone.utc)
    return base - timedelta(minutes=minutes_ago)


@pytest.fixture
def broker() -> EventBroker:
    return EventBroker()


@pytest.fixture
def handler() -> MagicMock:
    return MagicMock()


# ── Happy path ────────────────────────────────────────────────


class TestThresholdDetectorHappyPath:
    def test_fires_event_when_threshold_reached(
        self, broker: EventBroker, handler: MagicMock
    ) -> None:
        detector = ThresholdDetector(threshold=3, window_seconds=300)
        detector.register_broker(broker)
        broker.subscribe(handler)

        ip = "192.0.2.1"
        now = _utc()

        detector.record_attempt(ip, now - timedelta(seconds=10))
        detector.record_attempt(ip, now - timedelta(seconds=5))
        detector.record_attempt(ip, now)

        handler.assert_called_once()
        event: SecurityEvent = handler.call_args[0][0]
        assert event.ip == ip
        assert event.attempt_count == 3
        assert event.service == "ssh"

    def test_does_not_fire_below_threshold(
        self, broker: EventBroker, handler: MagicMock
    ) -> None:
        detector = ThresholdDetector(threshold=5, window_seconds=300)
        detector.register_broker(broker)
        broker.subscribe(handler)

        ip = "192.0.2.1"
        now = _utc()

        for i in range(3):
            detector.record_attempt(ip, now - timedelta(seconds=i * 10))

        handler.assert_not_called()

    def test_threshold_of_one_fires_immediately(
        self, broker: EventBroker, handler: MagicMock
    ) -> None:
        detector = ThresholdDetector(threshold=1, window_seconds=300)
        detector.register_broker(broker)
        broker.subscribe(handler)

        detector.record_attempt("10.0.0.1", _utc())

        handler.assert_called_once()
        event: SecurityEvent = handler.call_args[0][0]
        assert event.attempt_count == 1


# ── Edge cases ────────────────────────────────────────────────


class TestThresholdDetectorEdgeCases:
    def test_resets_counter_after_window_expires(
        self, broker: EventBroker, handler: MagicMock
    ) -> None:
        detector = ThresholdDetector(threshold=3, window_seconds=60)
        detector.register_broker(broker)
        broker.subscribe(handler)

        ip = "192.0.2.1"
        base = _utc()

        # 2 attempts — old
        detector.record_attempt(ip, base - timedelta(minutes=5))
        detector.record_attempt(ip, base - timedelta(minutes=4))

        # 2 attempts — still within window (relative to now)
        detector.record_attempt(ip, base - timedelta(seconds=30))
        detector.record_attempt(ip, base - timedelta(seconds=10))

        # Old attempts should be pruned; only 2 in window → no fire yet
        assert handler.call_count == 0

        # 3rd recent attempt pushes over threshold
        detector.record_attempt(ip, base)
        handler.assert_called_once()

    def test_tracks_multiple_ips_independently(
        self, broker: EventBroker, handler: MagicMock
    ) -> None:
        detector = ThresholdDetector(threshold=2, window_seconds=300)
        detector.register_broker(broker)
        broker.subscribe(handler)

        now = _utc()

        detector.record_attempt("1.1.1.1", now)
        detector.record_attempt("2.2.2.2", now)

        # Neither has reached threshold
        handler.assert_not_called()

        detector.record_attempt("1.1.1.1", now + timedelta(seconds=5))
        assert handler.call_count == 1
        assert handler.call_args[0][0].ip == "1.1.1.1"

        detector.record_attempt("2.2.2.2", now + timedelta(seconds=10))
        assert handler.call_count == 2
        assert handler.call_args[0][0].ip == "2.2.2.2"

    def test_fires_only_once_per_breach_cycle(
        self, broker: EventBroker, handler: MagicMock
    ) -> None:
        """After firing, the counter resets.  A single extra attempt should NOT
        re-fire; it takes a full threshold count again."""
        detector = ThresholdDetector(threshold=2, window_seconds=300)
        detector.register_broker(broker)
        broker.subscribe(handler)

        now = _utc()

        detector.record_attempt("192.0.2.1", now)
        detector.record_attempt("192.0.2.1", now + timedelta(seconds=5))
        assert handler.call_count == 1

        # Counter was reset after fire.  One more attempt → below threshold.
        detector.record_attempt("192.0.2.1", now + timedelta(seconds=10))
        assert handler.call_count == 1

        # Second attempt after reset → reaches threshold again, fires.
        detector.record_attempt("192.0.2.1", now + timedelta(seconds=15))
        assert handler.call_count == 2
