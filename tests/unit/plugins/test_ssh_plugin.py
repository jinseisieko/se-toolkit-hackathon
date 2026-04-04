"""Unit tests for SSHAuthPlugin (V2 migration from V1 SSHAuthLogParser).

Covers:
- Failed password for valid user → ParsedEntry with event_type="failed_auth"
- Failed password for invalid user → ParsedEntry with user extracted
- Failed publickey → ParsedEntry with event_type="failed_publickey"
- Non-matching lines return None
- Malformed timestamp fallback
- IPv6 flagged in meta
- Plugin registration + creation via ParserRegistry end-to-end
"""

from __future__ import annotations

from datetime import datetime, timezone
from ipaddress import IPv4Address, IPv6Address

import pytest

from src.adapters.parsers.plugins.ssh_auth import SSHAuthPlugin
from src.core.plugins.parser_plugin import Severity
from src.core.plugins.registry import ParserRegistry


@pytest.fixture
def plugin() -> SSHAuthPlugin:
    return SSHAuthPlugin()


@pytest.fixture
def registry() -> ParserRegistry:
    return ParserRegistry()


# ── Happy path ────────────────────────────────────────────────


class TestSSHAuthPluginHappyPath:
    def test_failed_password_valid_user(self, plugin: SSHAuthPlugin) -> None:
        line = (
            "Apr  4 12:00:01 server sshd[12345]: "
            "Failed password for root from 192.0.2.1 port 22 ssh2"
        )
        result = plugin.parse_line(line)

        assert result is not None
        assert result.ip == IPv4Address("192.0.2.1")
        assert result.user == "root"
        assert result.service == "ssh"
        assert result.event_type == "failed_auth"
        assert "port" in result.meta

    def test_failed_password_invalid_user(self, plugin: SSHAuthPlugin) -> None:
        line = (
            "Apr  4 12:00:01 server sshd[12345]: "
            "Failed password for invalid user admin from 10.0.0.1 port 22 ssh2"
        )
        result = plugin.parse_line(line)

        assert result is not None
        assert result.ip == IPv4Address("10.0.0.1")
        assert result.user == "admin"
        assert result.event_type == "failed_auth"

    def test_failed_publickey(self, plugin: SSHAuthPlugin) -> None:
        line = (
            "Apr  4 12:00:01 server sshd[12345]: "
            "Failed publickey for deploy from 172.16.0.5 port 22 ssh2"
        )
        result = plugin.parse_line(line)

        assert result is not None
        assert result.ip == IPv4Address("172.16.0.5")
        assert result.user == "deploy"
        assert result.event_type == "failed_publickey"

    def test_default_log_path(self, plugin: SSHAuthPlugin) -> None:
        assert plugin.default_log_path == "/var/log/auth.log"

    def test_plugin_name(self, plugin: SSHAuthPlugin) -> None:
        assert plugin.name == "ssh_auth"

    def test_get_indicators(self, plugin: SSHAuthPlugin) -> None:
        rules = plugin.get_indicators()

        assert len(rules) >= 1
        # Should have a rule for failed password
        rule_names = [r.name for r in rules]
        assert "ssh_failed_password" in rule_names


# ── Edge cases ────────────────────────────────────────────────


class TestSSHAuthPluginEdgeCases:
    def test_non_matching_line_returns_none(
        self, plugin: SSHAuthPlugin
    ) -> None:
        line = "Apr  4 12:00:01 server sshd[12345]: Accepted password for root from 1.2.3.4"
        assert plugin.parse_line(line) is None

    def test_empty_line_returns_none(self, plugin: SSHAuthPlugin) -> None:
        assert plugin.parse_line("") is None

    def test_whitespace_only_returns_none(self, plugin: SSHAuthPlugin) -> None:
        assert plugin.parse_line("   \n") is None

    def test_malformed_timestamp_uses_fallback(
        self, plugin: SSHAuthPlugin
    ) -> None:
        line = (
            "GARBAGE server sshd[12345]: "
            "Failed password for root from 192.0.2.1 port 22 ssh2"
        )
        result = plugin.parse_line(line)

        assert result is not None
        assert result.ip == IPv4Address("192.0.2.1")
        assert result.user == "root"
        # Fallback timestamp should be recent
        assert (datetime.now(timezone.utc) - result.timestamp).total_seconds() < 5

    def test_ipv6_flagged_in_meta(self, plugin: SSHAuthPlugin) -> None:
        line = (
            "Apr  4 12:00:01 server sshd[12345]: "
            "Failed password for root from 2001:db8::1 port 22 ssh2"
        )
        result = plugin.parse_line(line)

        assert result is not None
        assert result.user == "root"
        assert result.meta.get("ip_type") == "ipv6"

    def test_config_log_path_override(self) -> None:
        plugin = SSHAuthPlugin(config={"log_path": "/var/log/custom_auth.log"})
        assert plugin.default_log_path == "/var/log/custom_auth.log"

    def test_connection_closed_ignored(self, plugin: SSHAuthPlugin) -> None:
        line = "Apr  4 12:00:01 server sshd[12345]: Connection closed by 192.0.2.1 port 22"
        assert plugin.parse_line(line) is None

    def test_disconnect_ignored(self, plugin: SSHAuthPlugin) -> None:
        line = "Apr  4 12:00:01 server sshd[12345]: Disconnected from user root 192.0.2.1 port 22"
        assert plugin.parse_line(line) is None


# ── Registry integration ──────────────────────────────────────


class TestSSHAuthPluginRegistry:
    def test_register_and_create_via_registry(
        self, registry: ParserRegistry
    ) -> None:
        registry.register("ssh_auth", SSHAuthPlugin)
        plugin = registry.create("ssh_auth", {})

        assert isinstance(plugin, SSHAuthPlugin)
        assert plugin.name == "ssh_auth"

    def test_registry_with_config(
        self, registry: ParserRegistry
    ) -> None:
        registry.register("ssh_auth", SSHAuthPlugin)
        plugin = registry.create(
            "ssh_auth", {"log_path": "/var/log/secure"}
        )

        assert plugin.default_log_path == "/var/log/secure"

    def test_parse_through_registry(
        self, registry: ParserRegistry
    ) -> None:
        registry.register("ssh_auth", SSHAuthPlugin)
        plugin = registry.create("ssh_auth", {})

        line = (
            "Apr  4 12:00:01 server sshd[12345]: "
            "Failed password for root from 192.0.2.1 port 22 ssh2"
        )
        result = plugin.parse_line(line)

        assert result is not None
        assert result.service == "ssh"
        assert result.event_type == "failed_auth"
