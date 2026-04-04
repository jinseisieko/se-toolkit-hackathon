"""Unit tests for ConsoleChannel.

Covers:
- Name property
- Config validation (always valid)
- Send with GeoIP data present
- Send without GeoIP data
- Send with user field
- Send writes to stdout (not stderr by default)
- Send returns successful SendResult
"""

from __future__ import annotations

import asyncio
import io
from datetime import datetime, timezone
from ipaddress import IPv4Address
from typing import Any

from src.adapters.alerting.console import ConsoleChannel
from src.core.alerting.channel import SendResult
from src.core.enrichment.base import EnrichedEvent, GeoLocation


def _make_event(
    ip: str = "192.0.2.1",
    has_geo: bool = False,
    has_user: bool = True,
) -> EnrichedEvent:
    geo = GeoLocation(
        country_code="US",
        country_name="United States",
        city="New York",
        latitude=40.7,
        longitude=-74.0,
    ) if has_geo else None

    return EnrichedEvent(
        ip=IPv4Address(ip),
        timestamp=datetime(2026, 4, 4, 12, 0, 0, tzinfo=timezone.utc),
        service="ssh",
        event_type="failed_auth",
        raw_line="Failed password for root from 192.0.2.1",
        user="root" if has_user else None,
        geo=geo,
    )


class TestConsoleChannelName:
    def test_name_is_console(self) -> None:
        channel = ConsoleChannel()
        assert channel.name == "console"


class TestConsoleChannelValidateConfig:
    def test_empty_config_is_valid(self) -> None:
        channel = ConsoleChannel()
        assert channel.validate_config({}) is True

    def test_any_config_is_valid(self) -> None:
        channel = ConsoleChannel()
        assert channel.validate_config({"anything": "goes"}) is True


class TestConsoleChannelSend:
    def _run_send(
        self,
        event: EnrichedEvent,
        config: dict[str, Any] | None = None,
    ) -> tuple[SendResult, str]:
        """Send via ConsoleChannel and capture stdout output."""
        channel = ConsoleChannel()
        output = io.StringIO()
        config = config or {}

        # Patch stdout for capture
        import sys
        old_stdout = sys.stdout
        sys.stdout = output
        try:
            result = asyncio.run(channel.send(event, config))
        finally:
            sys.stdout = old_stdout

        return result, output.getvalue()

    def test_send_with_geoip_data(self) -> None:
        event = _make_event(has_geo=True)
        result, captured = self._run_send(event)

        assert result.success is True
        assert result.channel == "console"
        assert "US" in captured
        assert "New York" in captured

    def test_send_without_geoip_data(self) -> None:
        event = _make_event(has_geo=False)
        result, captured = self._run_send(event)

        assert result.success is True
        assert "US" not in captured
        assert "192.0.2.1" in captured

    def test_send_with_user_field(self) -> None:
        event = _make_event(has_user=True)
        _, captured = self._run_send(event)

        assert "User: root" in captured

    def test_send_without_user_field(self) -> None:
        event = _make_event(has_user=False)
        _, captured = self._run_send(event)

        assert "User:" not in captured

    def test_send_returns_success_result(self) -> None:
        event = _make_event()
        channel = ConsoleChannel()

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(channel.send(event, {}))
        finally:
            loop.close()

        assert isinstance(result, SendResult)
        assert result.success is True
        assert result.message == "Logged to console"

    def test_send_failed_auth_uses_red_icon(self) -> None:
        event = _make_event()
        _, captured = self._run_send(event)

        assert "\U0001f534" in captured  # red circle

    def test_send_failed_publickey_uses_yellow_icon(self) -> None:
        event = _make_event()
        # Override event_type
        event = EnrichedEvent(
            ip=event.ip,
            timestamp=event.timestamp,
            service=event.service,
            event_type="failed_publickey",
            raw_line=event.raw_line,
            user=event.user,
        )
        _, captured = self._run_send(event)

        assert "\U0001f7e1" in captured  # yellow circle
