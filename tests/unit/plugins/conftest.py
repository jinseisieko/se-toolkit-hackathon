"""Shared fixtures for plugin tests."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from ipaddress import IPv4Address
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest

from src.core.plugins.parser_plugin import (
    DetectionRule,
    LogParserPlugin,
    ParsedEntry,
    Severity,
)


@pytest.fixture
def sample_parsed_entry() -> ParsedEntry:
    return ParsedEntry(
        ip=IPv4Address("192.0.2.1"),
        timestamp=datetime(2026, 4, 4, 12, 0, 0, tzinfo=timezone.utc),
        service="ssh",
        user="root",
        event_type="failed_auth",
        raw_line="Failed password for root from 192.0.2.1 port 22 ssh2",
        meta={"port": "22"},
    )


@pytest.fixture
def sample_detection_rule() -> DetectionRule:
    return DetectionRule(
        name="ssh_brute_force",
        pattern=re.compile(r"Failed password"),
        severity=Severity.HIGH,
        threshold=5,
        window_seconds=300,
    )


class MockPlugin(LogParserPlugin):
    """A test plugin that does minimal work."""

    @property
    def name(self) -> str:
        return "mock_plugin"

    @property
    def default_log_path(self) -> str:
        return "/var/log/mock.log"

    def parse_line(self, line: str) -> Optional[ParsedEntry]:
        if "MOCK" in line:
            return ParsedEntry(
                ip=IPv4Address("10.0.0.1"),
                timestamp=datetime.now(timezone.utc),
                service="mock",
                user=None,
                event_type="mock_event",
                raw_line=line,
                meta={},
            )
        return None

    def get_indicators(self) -> List[DetectionRule]:
        return [
            DetectionRule(
                name="mock_detect",
                pattern=re.compile(r"MOCK"),
                severity=Severity.LOW,
                threshold=1,
                window_seconds=60,
            )
        ]


class FailingPlugin(LogParserPlugin):
    """A plugin whose __init__ raises an error."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        raise RuntimeError("Plugin init failed")

    @property
    def name(self) -> str:
        return "failing_plugin"

    @property
    def default_log_path(self) -> str:
        return "/var/log/failing.log"

    def parse_line(self, line: str) -> Optional[ParsedEntry]:
        return None

    def get_indicators(self) -> List[DetectionRule]:
        return []
