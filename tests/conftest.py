"""Shared fixtures for all tests."""

from __future__ import annotations

import pytest


@pytest.fixture
def sample_security_event() -> dict:
    """Return a dict of kwargs suitable for constructing a SecurityEvent."""
    return {
        "ip": "192.0.2.1",
        "attempt_count": 5,
        "log_line": "Failed password for root from 192.0.2.1 port 22 ssh2",
        "service": "ssh",
    }
