"""Unit tests for SSHAuthLogParser.

Covers:
- Failed password for valid user
- Failed password for invalid user
- Failed publickey attempt
- Non-matching lines return None
- Malformed timestamp fallback
- Empty / whitespace-only lines ignored
"""

from __future__ import annotations

import pytest

from src.adapters.parsers.ssh_auth import SSHAuthLogParser
from src.adapters.log_tail import ParsedEntry


@pytest.fixture
def parser() -> SSHAuthLogParser:
    return SSHAuthLogParser()


# ── Happy path ────────────────────────────────────────────────


class TestSSHAuthLogParserHappyPath:
    def test_failed_password_valid_user(self, parser: SSHAuthLogParser) -> None:
        line = (
            "Apr  4 12:00:01 server sshd[12345]: "
            "Failed password for root from 192.0.2.1 port 22 ssh2"
        )
        result = parser.parse_line(line)

        assert result is not None
        assert result.ip == "192.0.2.1"
        assert result.user == "root"
        assert "Failed password" in result.raw_line

    def test_failed_password_invalid_user(self, parser: SSHAuthLogParser) -> None:
        line = (
            "Apr  4 12:00:01 server sshd[12345]: "
            "Failed password for invalid user admin from 10.0.0.1 port 22 ssh2"
        )
        result = parser.parse_line(line)

        assert result is not None
        assert result.ip == "10.0.0.1"
        assert result.user == "admin"

    def test_failed_publickey(self, parser: SSHAuthLogParser) -> None:
        line = (
            "Apr  4 12:00:01 server sshd[12345]: "
            "Failed publickey for deploy from 172.16.0.5 port 22 ssh2"
        )
        result = parser.parse_line(line)

        assert result is not None
        assert result.ip == "172.16.0.5"
        assert result.user == "deploy"


# ── Edge cases ────────────────────────────────────────────────


class TestSSHAuthLogParserEdgeCases:
    def test_non_matching_line_returns_none(self, parser: SSHAuthLogParser) -> None:
        line = "Apr  4 12:00:01 server sshd[12345]: Accepted password for root from 1.2.3.4"
        assert parser.parse_line(line) is None

    def test_empty_line_returns_none(self, parser: SSHAuthLogParser) -> None:
        assert parser.parse_line("") is None

    def test_whitespace_only_returns_none(self, parser: SSHAuthLogParser) -> None:
        assert parser.parse_line("   \n") is None

    def test_malformed_timestamp_uses_fallback(self, parser: SSHAuthLogParser) -> None:
        """Line with unparseable timestamp should still extract IP/user."""
        line = (
            "GARBAGE_TIMESTAMP server sshd[12345]: "
            "Failed password for root from 192.0.2.1 port 22 ssh2"
        )
        result = parser.parse_line(line)

        assert result is not None
        assert result.ip == "192.0.2.1"
        assert result.user == "root"
        # Timestamp should be set (fallback to current time)
        assert result.timestamp is not None

    def test_metadata_contains_service_info(self, parser: SSHAuthLogParser) -> None:
        line = (
            "Apr  4 12:00:01 server sshd[12345]: "
            "Failed password for root from 192.0.2.1 port 54321 ssh2"
        )
        result = parser.parse_line(line)

        assert result is not None
        assert result.metadata.get("service") == "ssh"
        assert result.metadata.get("port") == "54321"

    def test_ipv6_address_skipped(self, parser: SSHAuthLogParser) -> None:
        """V1 only supports IPv4."""
        line = (
            "Apr  4 12:00:01 server sshd[12345]: "
            "Failed password for root from 2001:db8::1 port 22 ssh2"
        )
        result = parser.parse_line(line)

        # Should still parse but flag as non-IPv4
        assert result is not None
        assert result.user == "root"
        assert result.metadata.get("ip_type") == "ipv6"

    def test_connection_closed_line_ignored(self, parser: SSHAuthLogParser) -> None:
        line = "Apr  4 12:00:01 server sshd[12345]: Connection closed by 192.0.2.1 port 22"
        assert parser.parse_line(line) is None

    def test_disconnect_line_ignored(self, parser: SSHAuthLogParser) -> None:
        line = "Apr  4 12:00:01 server sshd[12345]: Disconnected from user root 192.0.2.1 port 22"
        assert parser.parse_line(line) is None
