"""Unit tests for EventBroker (Observer pattern).

Covers:
- Single handler receives published event
- Multiple handlers receive the same event
- Handler exceptions don't crash the broker (log and continue)
- No subscribers → publish is a no-op
- Same handler subscribed twice fires twice
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, call

import pytest

from src.core.events import EventBroker, SecurityEvent


def _make_event(**overrides: object) -> SecurityEvent:
    base: dict = {
        "ip": "192.0.2.1",
        "attempt_count": 5,
        "timestamp": datetime(2026, 4, 4, 12, 0, 0, tzinfo=timezone.utc),
        "log_line": "Failed password for root from 192.0.2.1 port 22 ssh2",
        "service": "ssh",
    }
    base.update(overrides)
    return SecurityEvent(**base)  # type: ignore[arg-type]


# ── Happy path ────────────────────────────────────────────────


class TestEventBrokerHappyPath:
    def test_single_handler_receives_event(self) -> None:
        broker = EventBroker()
        handler = MagicMock()
        broker.subscribe(handler)

        event = _make_event()
        broker.publish(event)

        handler.assert_called_once_with(event)

    def test_multiple_handlers_receive_same_event(self) -> None:
        broker = EventBroker()
        handler_a = MagicMock()
        handler_b = MagicMock()
        broker.subscribe(handler_a)
        broker.subscribe(handler_b)

        event = _make_event()
        broker.publish(event)

        handler_a.assert_called_once_with(event)
        handler_b.assert_called_once_with(event)

    def test_same_handler_subscribed_twice_fires_twice(self) -> None:
        broker = EventBroker()
        handler = MagicMock()
        broker.subscribe(handler)
        broker.subscribe(handler)

        event = _make_event()
        broker.publish(event)

        assert handler.call_count == 2
        assert handler.call_args_list == [call(event), call(event)]


# ── Edge cases ────────────────────────────────────────────────


class TestEventBrokerEdgeCases:
    def test_publish_with_no_subscribers_is_noop(self) -> None:
        broker = EventBroker()
        event = _make_event()
        # Should not raise
        broker.publish(event)

    def test_handler_exception_does_not_stop_remaining_handlers(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging

        broker = EventBroker()

        failing_handler = MagicMock(side_effect=ValueError("boom"))
        good_handler = MagicMock()

        broker.subscribe(failing_handler)
        broker.subscribe(good_handler)

        event = _make_event()
        with caplog.at_level(logging.ERROR, logger="src.core.events"):
            broker.publish(event)

        # Good handler still called
        good_handler.assert_called_once_with(event)

        # Exception was logged (caplog.text includes the full formatted output
        # with traceback, which contains the exception message "boom")
        assert "boom" in caplog.text
        assert len([r for r in caplog.records if r.levelno >= logging.ERROR]) >= 1

    def test_handler_exception_is_logged_at_error_level(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging

        broker = EventBroker()
        failing = MagicMock(side_effect=RuntimeError("fail"))
        broker.subscribe(failing)

        with caplog.at_level(logging.ERROR, logger="src.core.events"):
            broker.publish(_make_event())

        assert any(record.levelno >= logging.ERROR for record in caplog.records)
